export const DOCUMENT_TYPE_OPTIONS = [
  { value: 'passport', label: 'Паспорт' },
  { value: 'snils', label: 'СНИЛС' },
  { value: 'inn_certificate', label: 'Свидетельство ИНН' },
  { value: 'children_birth_cert', label: 'Свидетельство о рождении детей' },
  { value: 'marriage_cert', label: 'Свидетельство о браке/расторжении' },
  { value: 'employment_history', label: 'Справка о трудовой деятельности' },
  { value: 'pension_account', label: 'Справка о лицевом счёте ПФ' },
  { value: 'tax_registry', label: 'Выписка ЕГРН' },
  { value: 'no_ip_status', label: 'Справка об отсутствии ИП' },
  { value: 'ndfl_2', label: 'Справки 2-НДФЛ' },
  { value: 'tax_debt', label: 'Справка об исполнении обязанностей по налогам' },
  { value: 'credit_debt', label: 'Справка о задолженности по кредитам' },
  { value: 'credit_agreements', label: 'Копии кредитных договоров' },
  { value: 'court_fee', label: 'Квитанция госпошлины' },
  { value: 'criminal_record', label: 'Справка о судимости' },
  { value: 'deposit_payment', label: 'Квитанция на депозит' },
  { value: 'uritech_review', label: 'На проверку от ЮРИТЕХ' },
  { value: 'other', label: 'Прочее' },
] as const;

export const DOCUMENT_TYPE_LABELS: Record<string, string> = Object.fromEntries(
  DOCUMENT_TYPE_OPTIONS.map((option) => [option.value, option.label]),
);

export function documentTypeLabel(value: string | null | undefined): string {
  if (!value) return 'Документ';
  return DOCUMENT_TYPE_LABELS[value] ?? value;
}
