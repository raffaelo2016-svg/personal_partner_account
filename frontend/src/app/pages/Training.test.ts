import { describe, expect, it } from 'vitest';
import {
  TRAINING_FAQ,
  TRAINING_INSTRUCTIONS,
  TRAINING_LESSONS,
  TRAINING_NOTES,
  TRAINING_TOTAL_DURATION,
  findLesson,
  formatLessonDuration,
} from '../data/trainingCourse';

describe('курс обучения', () => {
  it('содержит шесть уроков', () => {
    expect(TRAINING_LESSONS).toHaveLength(6);
  });

  it('нумерует уроки по порядку без пропусков', () => {
    expect(TRAINING_LESSONS.map((lesson) => lesson.number)).toEqual([1, 2, 3, 4, 5, 6]);
  });

  it('использует уникальные ключи и адреса видео', () => {
    const keys = TRAINING_LESSONS.map((lesson) => lesson.key);
    const urls = TRAINING_LESSONS.map((lesson) => lesson.videoUrl);
    expect(new Set(keys).size).toBe(keys.length);
    expect(new Set(urls).size).toBe(urls.length);
  });

  it('отдаёт видео из самого кабинета, а не с внешнего сервиса', () => {
    for (const lesson of TRAINING_LESSONS) {
      expect(lesson.videoUrl.startsWith('/training/')).toBe(true);
      expect(lesson.videoUrl.endsWith('.mp4')).toBe(true);
    }
  });

  it('у каждого урока есть конспект и шаги', () => {
    for (const lesson of TRAINING_LESSONS) {
      expect(lesson.conspect.length).toBeGreaterThan(2);
      expect(lesson.steps.length).toBeGreaterThan(0);
      expect(lesson.title.length).toBeGreaterThan(3);
      expect(lesson.duration).toBeGreaterThan(0);
      expect(lesson.duration).toBeLessThan(180);
    }
  });

  it('ссылки уроков ведут внутрь кабинета', () => {
    for (const lesson of TRAINING_LESSONS) {
      expect(lesson.section.to.startsWith('/dashboard')).toBe(true);
      for (const step of lesson.steps) {
        if (step.to) expect(step.to.startsWith('/dashboard')).toBe(true);
      }
    }
  });

  it('суммарная длительность совпадает с суммой уроков', () => {
    const sum = TRAINING_LESSONS.reduce((total, lesson) => total + lesson.duration, 0);
    expect(TRAINING_TOTAL_DURATION).toBe(sum);
  });
});

describe('вспомогательные функции', () => {
  it('находит урок по ключу', () => {
    expect(findLesson('intro')?.title).toBe('Как устроен кабинет');
    expect(findLesson('unknown')).toBeUndefined();
  });

  it('форматирует длительность как м:сс', () => {
    expect(formatLessonDuration(43)).toBe('0:43');
    expect(formatLessonDuration(269)).toBe('4:29');
    expect(formatLessonDuration(0)).toBe('0:00');
    expect(formatLessonDuration(-5)).toBe('0:00');
  });
});

describe('справочные материалы', () => {
  it('в FAQ нет пустых вопросов и ответов', () => {
    expect(TRAINING_FAQ.length).toBeGreaterThan(4);
    for (const item of TRAINING_FAQ) {
      expect(item.question.trim().length).toBeGreaterThan(5);
      expect(item.answer.trim().length).toBeGreaterThan(10);
    }
  });

  it('у каждого важного пункта есть иконка из известного набора', () => {
    const allowed = ['alert', 'warning', 'info', 'default'];
    for (const note of TRAINING_NOTES) {
      expect(allowed).toContain(note.icon);
    }
  });

  it('в инструкциях есть шаги', () => {
    for (const instruction of TRAINING_INSTRUCTIONS) {
      expect(instruction.steps.length).toBeGreaterThan(1);
    }
  });
});

describe('фильтр FAQ', () => {
  function filterFaq(query: string) {
    const q = query.trim().toLowerCase();
    if (!q) return TRAINING_FAQ;
    return TRAINING_FAQ.filter(
      (item) =>
        item.question.toLowerCase().includes(q) || item.answer.toLowerCase().includes(q),
    );
  }

  it('пустой запрос возвращает всё', () => {
    expect(filterFaq('')).toHaveLength(TRAINING_FAQ.length);
  });

  it('ищет по вопросу и ответу без учёта регистра', () => {
    expect(filterFaq('ОПЛАТ').length).toBeGreaterThan(0);
    expect(filterFaq('формат').length).toBeGreaterThan(0);
  });

  it('не находит несуществующее', () => {
    expect(filterFaq('ипотека в швейцарии')).toHaveLength(0);
  });
});
