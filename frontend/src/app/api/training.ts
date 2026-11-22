import apiClient from './client';

export interface TrainingVideoData {
  id: string;
  title: string;
  description: string | null;
  duration: number | null;
  video_url: string;
  thumbnail_url: string | null;
  order: number;
  created_at: string;
}

export interface FAQData {
  id: string;
  question: string;
  answer: string;
  order: number;
  created_at: string;
}

export interface InstructionData {
  id: string;
  title: string;
  steps: { items: string[] };
  order: number;
  created_at: string;
}

export interface ImportantNoteData {
  id: string;
  title: string;
  description: string;
  icon: string | null;
  order: number;
  created_at: string;
}

export async function fetchTrainingVideos(): Promise<TrainingVideoData[]> {
  const { data } = await apiClient.get('/training/videos');
  return data;
}

export async function fetchFAQ(): Promise<FAQData[]> {
  const { data } = await apiClient.get('/training/faq');
  return data;
}

export async function fetchInstructions(): Promise<InstructionData[]> {
  const { data } = await apiClient.get('/training/instructions');
  return data;
}

export async function fetchImportantNotes(): Promise<ImportantNoteData[]> {
  const { data } = await apiClient.get('/training/important');
  return data;
}

/** Ключи уроков, которые партнёр уже посмотрел. */
export async function fetchTrainingProgress(): Promise<string[]> {
  const { data } = await apiClient.get<{ completed: string[] }>('/training/progress');
  return data.completed;
}

export async function completeTrainingLesson(lessonKey: string): Promise<string[]> {
  const { data } = await apiClient.put<{ completed: string[] }>(
    `/training/progress/${encodeURIComponent(lessonKey)}`,
  );
  return data.completed;
}

export async function resetTrainingLesson(lessonKey: string): Promise<string[]> {
  const { data } = await apiClient.delete<{ completed: string[] }>(
    `/training/progress/${encodeURIComponent(lessonKey)}`,
  );
  return data.completed;
}
