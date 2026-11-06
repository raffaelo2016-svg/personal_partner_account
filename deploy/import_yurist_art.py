"""Create internal Yurist-Art card linked to Bitrix 18 and two approved clients.

No fabricated contacts; the backing user has an empty login and is inactive.
No remote partner mutation. Client creation is queued only after duplicate checks.
"""

import argparse
import ast
import subprocess
import sys
from pathlib import Path

WORKER = r'''
import asyncio,json,re,secrets
from datetime import UTC,datetime
from uuid import uuid5
from sqlalchemy import select,func,or_,text
from app.config import settings
from app.database import async_session
from app.core.security import hash_password
from app.models.user import User
from app.models.partner import Partner
from app.models.client import Client
from app.models.court_fee import CourtFee
from app.models.audit_log import AuditLog
from app.models.bitrix_sync import BitrixEntityMap,BitrixOutboxOperation
from app.integrations.bitrix24.partners import (
    PARTNER_ENTITY_TYPE,PARTNER_FIELDS,active_installation,_installation_token,
    _remote_value,partner_profile_differences,
)
from app.integrations.bitrix24.clients import schedule_client_creation,CLIENT_DEAL_FIELDS
from app.integrations.bitrix24.client import Bitrix24Client
from app.services.chat_service import ensure_rooms_for_partner
from app.services import finance_service

IMPORT_ID='yurist-art-october-2026-two-clients-v1'
ROWS=[
 {'full_name':'Сидельникова Елена Викторовна','case_number':'А14-16441/2026','hearing_date':'2026-11-23','source_row':25,
  'case_url':'https://kad.arbitr.ru/Card/eb01b4c8-c6bb-4d57-af07-52494311980d'},
 {'full_name':'Татаренко Всеволод Александрович','case_number':'А14-12592/2026','hearing_date':'2027-01-13','source_row':26,
  'case_url':'https://kad.arbitr.ru/Card/47b9af95-4b12-47e0-a090-d569f258c3fb'},
]
def norm(value):
 return re.sub(r'[^а-яa-z0-9]','',str(value or '').casefold().replace('ё','е').replace('a','а'))
def meta(client):
 return (client.document_generation_data or {}).get('source_import',{})

async def main():
 async with async_session() as db:
  try:
   await db.execute(text("SELECT pg_advisory_xact_lock(hashtext('cabinet:link:yurist-art:18'))"))
   inst=await active_installation(db)
   if inst is None:raise RuntimeError('Bitrix installation missing')
   token=await _installation_token(db,inst)
   async with Bitrix24Client(inst.client_endpoint,token) as remote:
    item=(await remote.call('crm.item.get',{'entityTypeId':settings.BITRIX_SMART_PROCESS_ENTITY_TYPE_ID,'id':18,'useOriginalUfNames':'Y'}))['item']
    if item.get('title')!='Юрист-Арт' or _remote_value(item,PARTNER_FIELDS['director_name'])!='Щукина Ольга Викторовна':
     raise RuntimeError('Bitrix partner identity changed')
    matches_result=await db.scalars(select(Partner).where(or_(Partner.bitrix_partner_item_id=='18',Partner.company_name.ilike('%юрист%арт%'))))
    matches=list(matches_result.all())
    remote_type=f'crm_dynamic_{settings.BITRIX_SMART_PROCESS_ENTITY_TYPE_ID}'
    mapping=await db.scalar(select(BitrixEntityMap).where(BitrixEntityMap.member_id==inst.member_id,BitrixEntityMap.bitrix_entity_type==remote_type,BitrixEntityMap.bitrix_entity_id=='18'))
    if matches:
     if len(matches)!=1:raise RuntimeError('Several cabinet partner matches')
     partner=matches[0];user=await db.get(User,partner.user_id)
     if (partner.deleted_at is not None or partner.bitrix_partner_item_id!='18' or
         mapping is None or mapping.local_entity_id!=partner.id or user.is_active or user.email!='' or
         partner.phone!='' or partner.court_fee_per_client!=1700000 or partner.payment_term_days!=10):
      raise RuntimeError('Existing cabinet partner differs; refusing overwrite')
     partner_created=False
    else:
     if mapping:raise RuntimeError('Bitrix partner already mapped elsewhere')
     if await db.scalar(select(User.id).where(User.email=='')):
      raise RuntimeError('An empty-login internal account already exists; no changes made')
     user=User(email='',hashed_password=hash_password(secrets.token_urlsafe(32)),role='partner',is_active=False)
     db.add(user);await db.flush()
     partner=Partner(user_id=user.id,company_name='Юрист-Арт',director_name='Щукина Ольга Викторовна',
       partner_type='individual',inn='',phone='',court_fee_per_client=1700000,payment_term_days=10,
       free_client_limit=0,status='active',bitrix_partner_item_id='18',bitrix_sync_status='conflict',
       bitrix_sync_error_code='REMOTE_PROFILE_CHANGED')
     db.add(partner);await db.flush()
     await ensure_rooms_for_partner(db,str(partner.id))
     db.add(BitrixEntityMap(member_id=inst.member_id,local_entity_type=PARTNER_ENTITY_TYPE,
       local_entity_id=partner.id,bitrix_entity_type=remote_type,bitrix_entity_id='18',last_verified_at=datetime.now(UTC)))
     db.add(AuditLog(action='create_internal_partner_link_existing_bitrix',target_id=str(partner.id),target_type='partner',
       details={'remote_id':'18','internal_only':True,'contacts_unknown':True,'login_enabled':False,
                'court_fee_rub':17000,'payment_days':10,'remote_partner_mutations':False}))
     partner_created=True

    all_clients=list((await db.scalars(select(Client))).all())
    existing={}
    for row in ROWS:
     found=[c for c in all_clients if norm(c.case_number)==norm(row['case_number']) or norm(c.full_name)==norm(row['full_name'])]
     if found:
      if len(found)!=1:raise RuntimeError('Multiple client matches: '+row['full_name'])
      c=found[0]
      if (c.deleted_at is not None or c.partner_id!=partner.id or meta(c).get('import_id')!=IMPORT_ID or
          norm(c.case_number)!=norm(row['case_number']) or norm(c.full_name)!=norm(row['full_name'])):
       raise RuntimeError('Existing client requires review: '+row['full_name'])
      existing[row['case_number']]=c
     else:
      for filters in [{'%TITLE':row['full_name']},{'%'+CLIENT_DEAL_FIELDS['case_number']:row['case_number'].split('-')[1]}]:
       deals=await remote.call('crm.deal.list',{'filter':filters,'select':['ID','TITLE',CLIENT_DEAL_FIELDS['case_number']]})
       exact=[d for d in deals if norm(d.get(CLIENT_DEAL_FIELDS['case_number']))==norm(row['case_number']) or norm(row['full_name']) in norm(d.get('TITLE'))]
       if exact:raise RuntimeError('Existing Bitrix deal requires linking, not creation: '+row['full_name'])
      last,first,middle=row['full_name'].split()
      contacts=await remote.call('crm.contact.list',{'filter':{'%LAST_NAME':last,'%NAME':first},'select':['ID','LAST_NAME','NAME','SECOND_NAME']})
      if any(norm(' '.join(str(c.get(k) or '') for k in ['LAST_NAME','NAME','SECOND_NAME']))==norm(row['full_name']) for c in contacts):
       raise RuntimeError('Existing Bitrix contact requires linking: '+row['full_name'])

    def tx_audit(action,**kwargs):db.add(AuditLog(action=action,**kwargs))
    finance_service.audit_log=tx_audit
    clients=list(existing.values());created=0
    for row in ROWS:
     if row['case_number'] in existing:continue
     c=Client(id=uuid5(partner.id,IMPORT_ID+':'+row['case_number']),partner_id=partner.id,
       type='in_court',status='waiting_hearing',document_preparation_mode='uritech',full_name=row['full_name'],
       case_number=row['case_number'],region='Воронежская область',court_procedure_date=None,
       document_generation_data={'source_import':{'import_id':IMPORT_ID,'source_filename':'октябрь новые люди (1).xlsx',
         'source_sheet':'Лист1','source_row':row['source_row'],'original_status':'Рассмотрение дела',
         'hearing_date':row['hearing_date'],'case_url':row['case_url']}})
     db.add(c);await db.flush()
     await finance_service.create_court_fee_for_client(db,c,partner)
     await schedule_client_creation(db,c,partner=partner)
     await db.refresh(c);clients.append(c);created+=1
     db.add(AuditLog(action='import_client',target_id=str(c.id),target_type='client',details={'import_id':IMPORT_ID,'hearing_date':row['hearing_date']}))
    await db.flush()
    partner_queue=await db.scalar(select(func.count()).select_from(BitrixOutboxOperation).where(
      BitrixOutboxOperation.local_entity_type==PARTNER_ENTITY_TYPE,
      BitrixOutboxOperation.local_entity_id==partner.id,BitrixOutboxOperation.bitrix_method=='crm.item.add'))
    if partner_queue:raise RuntimeError('Unexpected partner creation queue; rollback')
    total=0;due_dates=set()
    for c in clients:
     fees=list((await db.scalars(select(CourtFee).where(CourtFee.client_id==c.id,CourtFee.deleted_at.is_(None)))).all())
     if len(fees)!=1 or fees[0].amount!=1700000 or c.court_procedure_date is not None:
      raise RuntimeError('Client fee/procedure verification failed')
     total+=fees[0].amount;due_dates.add(fees[0].due_date.isoformat())
     print('CLIENT_OK',c.full_name,c.case_number,'hearing='+meta(c)['hearing_date'],'id='+str(c.id),flush=True)
    if len(clients)!=2 or total!=3400000:raise RuntimeError('Expected two clients and 34000 RUB')
    partner_id=str(partner.id)
    print(json.dumps({'partner_id':partner_id,'partner_created':partner_created,'partner_bitrix_id':'18',
      'client_created':created,'clients_verified':len(clients),'fees_rub':total//100,'fee_due_dates':sorted(due_dates),
      'login_enabled':user.is_active,'email':user.email,'phone':partner.phone,'partner_creation_queue':partner_queue},ensure_ascii=False),flush=True)
    if APPLY:await db.commit()
    else:
     await db.rollback();print('DRY_RUN_OK: all changes rolled back',flush=True);return
  except BaseException:
   await db.rollback();raise
 async with async_session() as db:
  partner=await db.get(Partner,partner_id);user=await db.get(User,partner.user_id)
  saved=list((await db.scalars(select(Client).where(Client.partner_id==partner.id,Client.deleted_at.is_(None)))).all())
  saved=[c for c in saved if meta(c).get('import_id')==IMPORT_ID]
  if len(saved)!=2 or user.is_active or user.email!='' or partner.phone!='' or partner.bitrix_partner_item_id!='18':
   raise RuntimeError('Post-commit validation failed')
  for row in ROWS:
   matches=[c for c in saved if c.case_number==row['case_number'] and c.full_name==row['full_name']]
   if len(matches)!=1 or meta(matches[0])['hearing_date']!=row['hearing_date']:raise RuntimeError('Source verification failed')
  print('IMPORT_OK: internal Yurist-Art linked to existing Bitrix 18; two clients verified; no partner duplicate; login disabled',flush=True)

asyncio.run(main())
'''


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--apply", action="store_true")
    args = parser.parse_args()
    for apply in ([False, True] if args.apply else [False]):
        code = "APPLY=" + repr(apply) + "\n" + WORKER
        ast.parse(code)
        subprocess.run([sys.executable, str(Path(__file__).with_name("remote_access.py")), "ssh",
                        "docker", "compose", "-f", "/srv/personal_partner_account/docker-compose.prod.yml",
                        "exec", "-T", "backend", "python", "-"], input=code, text=True, check=True)


if __name__ == "__main__":
    main()
