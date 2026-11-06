"""Create an internal SvoyYurist partner linked to existing Bitrix item 47.

Only crm.item.get/list are used remotely. No Bitrix create/update is issued.
Default run rolls back; --apply rehearses, commits, then verifies the linkage.
"""

import argparse
import ast
import subprocess
import sys
from pathlib import Path

WORKER = r'''
import asyncio,json,re,secrets
from datetime import UTC,datetime
from sqlalchemy import select,func,or_,text
from app.config import settings
from app.database import async_session
from app.core.security import hash_password
from app.models.user import User
from app.models.partner import Partner
from app.models.audit_log import AuditLog
from app.models.bitrix_sync import BitrixEntityMap,BitrixOutboxOperation
from app.integrations.bitrix24.partners import (
    PARTNER_ENTITY_TYPE,PARTNER_FIELDS,active_installation,_installation_token,
    _remote_value,partner_profile_differences,
)
from app.integrations.bitrix24.client import Bitrix24Client
from app.services.chat_service import ensure_rooms_for_partner

NAME="ООО СвойЮрист"
EMAIL="partner-bitrix-47@no-login.invalid"
PHONE="+79026541787"
REMOTE_ID="47"

async def remote_snapshot(db,inst):
    token=await _installation_token(db,inst)
    async with Bitrix24Client(inst.client_endpoint,token) as remote:
        result=await remote.call('crm.item.list',{
            'entityTypeId':settings.BITRIX_SMART_PROCESS_ENTITY_TYPE_ID,
            'filter':{'%title':'ООО СвойЮрист'},'select':['*'],'useOriginalUfNames':'Y',
        })
    items=result.get('items',[])
    matches=[i for i in items if str(i.get('id'))==REMOTE_ID]
    if len(matches)!=1:
        raise RuntimeError('Existing Bitrix item 47 not found uniquely')
    item=matches[0]
    if item.get('title')!=NAME or str(_remote_value(item,PARTNER_FIELDS['email']) or '').strip()!='':
        raise RuntimeError('Existing Bitrix identity differs from the reviewed card')
    phone=str(_remote_value(item,PARTNER_FIELDS['phone']) or '')
    if phone != 'телефона для связи - 89026541787, мессенджер - 89377046022':
        raise RuntimeError('Existing Bitrix phone differs')
    return item,{str(i['id']) for i in items}

async def main():
    async with async_session() as db:
        try:
            await db.execute(text("SELECT pg_advisory_xact_lock(hashtext('cabinet:link:svoyyurist:47'))"))
            inst=await active_installation(db)
            if inst is None:raise RuntimeError('Active Bitrix installation missing')
            remote_item,before_ids=await remote_snapshot(db,inst)
            remote_type=f'crm_dynamic_{settings.BITRIX_SMART_PROCESS_ENTITY_TYPE_ID}'
            links=list((await db.scalars(select(BitrixEntityMap).where(
                BitrixEntityMap.member_id==inst.member_id,
                BitrixEntityMap.bitrix_entity_type==remote_type,
                BitrixEntityMap.bitrix_entity_id==REMOTE_ID,
            ))).all())
            matches=(await db.execute(select(Partner,User).join(User,User.id==Partner.user_id).where(or_(
                func.lower(User.email)==EMAIL,Partner.company_name==NAME,
                Partner.phone==PHONE,Partner.bitrix_partner_item_id==REMOTE_ID,
            )))).all()
            if matches:
                if len(matches)!=1:raise RuntimeError('Multiple cabinet identity matches')
                partner,user=matches[0]
                if (partner.deleted_at is not None or user.email.casefold()!=EMAIL or
                    partner.bitrix_partner_item_id!=REMOTE_ID or len(links)!=1 or
                    links[0].local_entity_id!=partner.id):
                    raise RuntimeError('Existing cabinet account requires review; no changes made')
                created=False
            else:
                if links:raise RuntimeError('Bitrix item already linked to another cabinet record')
                if await db.scalar(select(User.id).where(func.lower(User.email)==EMAIL)):
                    raise RuntimeError('Email belongs to an existing account')
                user=User(email=EMAIL,hashed_password=hash_password(secrets.token_urlsafe(32)),
                          role='partner',is_active=False)
                db.add(user);await db.flush()
                partner=Partner(
                    user_id=user.id,partner_type='legal',company_name=NAME,director_name='Таякина Светлана Юрьевна',
                    inn='',phone=PHONE,legal_address=None,court_fee_per_client=1700000,payment_term_days=10,
                    free_client_limit=0,status='active',bitrix_partner_item_id=REMOTE_ID,
                    bitrix_sync_status='not_scheduled',
                )
                db.add(partner);await db.flush()
                await ensure_rooms_for_partner(db,str(partner.id))
                differences=await partner_profile_differences(db,partner,remote_item)
                now=datetime.now(UTC)
                partner.bitrix_sync_status='conflict' if differences else 'synced'
                partner.bitrix_sync_error_code='REMOTE_PROFILE_CHANGED' if differences else None
                db.add(BitrixEntityMap(
                    member_id=inst.member_id,local_entity_type=PARTNER_ENTITY_TYPE,
                    local_entity_id=partner.id,bitrix_entity_type=remote_type,
                    bitrix_entity_id=REMOTE_ID,last_verified_at=now,
                ))
                db.add(AuditLog(action='create_partner_link_existing_bitrix',target_type='partner',
                    target_id=str(partner.id),details={'remote_id':REMOTE_ID,'remote_mutations':False,'internal_account':True,'login_enabled':False,
                        'court_fee_rub':17000,'payment_term_days':10,'free_client_limit':0,
                        'source_contact_phone':'89026541787','source_messenger_phone':'89377046022','remote_profile_differences':sorted(differences)}))
                created=True
            await db.flush();await db.refresh(partner)
            if user.is_active:raise RuntimeError("Internal partner login must remain disabled")
            queued=await db.scalar(select(func.count()).select_from(BitrixOutboxOperation).where(
                BitrixOutboxOperation.local_entity_type==PARTNER_ENTITY_TYPE,
                BitrixOutboxOperation.local_entity_id==partner.id,
                BitrixOutboxOperation.bitrix_method=='crm.item.add',
            ))
            if queued:raise RuntimeError('Unexpected Bitrix creation queue entry; refusing commit')
            partner_id=str(partner.id)
            print(json.dumps({'created':created,'partner_id':partner_id,'name':partner.company_name,
                'email':None,'login_enabled':user.is_active,'phone':partner.phone,'court_fee_rub':partner.court_fee_per_client//100,
                'payment_days':partner.payment_term_days,'remote_id':REMOTE_ID,'creation_queue_entries':queued,
                'sync_status':partner.bitrix_sync_status,'smtp_configured':bool(settings.SMTP_HOST)},ensure_ascii=False),flush=True)
            if not APPLY:
                await db.rollback();print('DRY_RUN_OK: no changes saved',flush=True);return
            await db.commit()
        except BaseException:
            await db.rollback();raise
    async with async_session() as db:
        partner=await db.get(Partner,partner_id)
        if partner is None or partner.bitrix_partner_item_id!=REMOTE_ID:
            raise RuntimeError('Post-commit cabinet check failed')
        inst=await active_installation(db)
        _,after_ids=await remote_snapshot(db,inst)
        if before_ids!=after_ids:raise RuntimeError('Bitrix matching item set changed; review needed')
        print('LINK_OK: cabinet partner saved; linked existing Bitrix item 47; no duplicate or remote edits',flush=True)

asyncio.run(main())
'''


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--apply", action="store_true")
    args = parser.parse_args()
    remote = Path(__file__).with_name("remote_access.py")
    for apply in ([False, True] if args.apply else [False]):
        code = "APPLY=" + repr(apply) + "\n" + WORKER
        ast.parse(code)
        subprocess.run([sys.executable, str(remote), "ssh", "docker", "compose", "-f",
                        "/srv/personal_partner_account/docker-compose.prod.yml", "exec", "-T",
                        "backend", "python", "-"], input=code, text=True, check=True)


if __name__ == "__main__":
    main()
