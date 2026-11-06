"""Import approved Filippovich client for existing SvoyYurist partner."""
import argparse
import ast
import subprocess
import sys
from pathlib import Path

WORKER = r'''
import asyncio,json,re
from uuid import UUID,uuid5
from sqlalchemy import select,text
from app.database import async_session
from app.models.partner import Partner
from app.models.client import Client
from app.models.court_fee import CourtFee
from app.models.audit_log import AuditLog
from app.integrations.bitrix24.partners import active_installation,_installation_token
from app.integrations.bitrix24.client import Bitrix24Client
from app.integrations.bitrix24.clients import schedule_client_creation
from app.services import finance_service
NAME='Филиппович Игорь Валерьевич'
IMPORT='svoyyurist-filippovich-oct2026-v1'
PID=UUID('827343ef-9b96-4c4f-bf11-bfb220e32855')
def norm(s):return re.sub(r'[^а-яa-z0-9]','',str(s or '').casefold().replace('ё','е'))
async def main():
 async with async_session() as db:
  try:
   await db.execute(text("SELECT pg_advisory_xact_lock(hashtext('cabinet:import:filippovich:2026'))"))
   p=await db.get(Partner,PID)
   if p is None or p.deleted_at is not None or p.bitrix_partner_item_id!='47' or p.court_fee_per_client!=1700000:raise RuntimeError('Partner mismatch')
   cs=list((await db.scalars(select(Client))).all())
   found=[c for c in cs if norm(c.full_name)==norm(NAME)]
   if found:
    if len(found)!=1 or found[0].partner_id!=PID or (found[0].document_generation_data or {}).get('source_import',{}).get('import_id')!=IMPORT or found[0].deleted_at is not None:raise RuntimeError('Existing client requires review')
    c=found[0];created=False
   else:
    inst=await active_installation(db);token=await _installation_token(db,inst)
    async with Bitrix24Client(inst.client_endpoint,token) as bx:
     deals=await bx.call('crm.deal.list',{'filter':{'%TITLE':'Филиппович'},'select':['ID','TITLE']})
     contacts=await bx.call('crm.contact.list',{'filter':{'%LAST_NAME':'Филиппович'},'select':['ID','LAST_NAME','NAME','SECOND_NAME']})
     if any(norm(NAME) in norm(d.get('TITLE')) for d in deals):raise RuntimeError('Existing Bitrix deal needs linking')
     if any(norm(' '.join(str(c.get(k) or '') for k in ['LAST_NAME','NAME','SECOND_NAME']))==norm(NAME) for c in contacts):raise RuntimeError('Existing Bitrix contact needs linking')
    c=Client(id=uuid5(PID,IMPORT),partner_id=PID,full_name=NAME,type='before_court',status='sent_to_court',document_preparation_mode='uritech',region='Нижегородская область',case_number=None,court_procedure_date=None,document_generation_data={'source_import':{'import_id':IMPORT,'source_row':30,'original_status':'Документы отправлены','documents_sent_date':'2026-10-16','date_interpretation':'Дата отправки документов по строке пользователя; не дата заседания'}})
    db.add(c);await db.flush()
    def tx_audit(action,**kwargs):db.add(AuditLog(action=action,**kwargs))
    finance_service.audit_log=tx_audit
    await finance_service.create_court_fee_for_client(db,c,p)
    await schedule_client_creation(db,c,partner=p)
    db.add(AuditLog(action='import_client',target_type='client',target_id=str(c.id),details={'import_id':IMPORT,'documents_sent_date':'2026-10-16'}))
    created=True
   await db.flush();await db.refresh(c)
   fees=list((await db.scalars(select(CourtFee).where(CourtFee.client_id==c.id,CourtFee.deleted_at.is_(None)))).all())
   if len(fees)!=1 or fees[0].amount!=1700000 or c.status!='sent_to_court' or c.case_number is not None:raise RuntimeError('Verification failed')
   print(json.dumps({'id':str(c.id),'name':c.full_name,'created':created,'status':c.status,'fee_rub':fees[0].amount//100,'due_date':str(fees[0].due_date),'bitrix_sync_status':c.bitrix_sync_status},ensure_ascii=False),flush=True)
   if APPLY:await db.commit()
   else:await db.rollback();print('DRY_RUN_OK',flush=True);return
  except BaseException:await db.rollback();raise
 async with async_session() as db:
  c=await db.get(Client,uuid5(PID,IMPORT))
  assert c is not None and c.partner_id==PID and c.document_generation_data['source_import']['documents_sent_date']=='2026-10-16'
  print('IMPORT_OK: persisted client verified',flush=True)
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
