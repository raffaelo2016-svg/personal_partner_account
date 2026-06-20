import { describe, expect, it } from 'vitest';

describe('training tabs', () => {
  const TABS = ['videos', 'faq', 'instructions', 'important'] as const;

  it('has 4 tabs', () => expect(TABS).toHaveLength(4));

  it.each(TABS)('tab %s is valid string', (tab) => {
    expect(typeof tab).toBe('string');
    expect(tab.length).toBeGreaterThan(0);
  });
});

describe('FAQ search filter', () => {
  interface FAQ { question: string; answer: string }

  function filterFaq(items: FAQ[], query: string): FAQ[] {
    if (!query) return items;
    const q = query.toLowerCase();
    return items.filter((f) => f.question.toLowerCase().includes(q) || f.answer.toLowerCase().includes(q));
  }

  const data: FAQ[] = [
    { question: 'Как подать заявление?', answer: 'Через личный кабинет' },
    { question: 'Сроки рассмотрения', answer: '30 рабочих дней' },
  ];

  it('empty query → all', () => expect(filterFaq(data, '')).toHaveLength(2));
  it('match question', () => expect(filterFaq(data, 'заявление')).toHaveLength(1));
  it('match answer', () => expect(filterFaq(data, 'кабинет')).toHaveLength(1));
  it('no match', () => expect(filterFaq(data, 'xyz')).toHaveLength(0));
  it('case insensitive', () => expect(filterFaq(data, 'СРОКИ')).toHaveLength(1));
});
