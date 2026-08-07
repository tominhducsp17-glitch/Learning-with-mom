import type { Assignment, AssignmentAnalytics, AssignmentResults, ClassroomRoster, ExamDraft, Overview, ParsedExam, SubmissionResult } from "./types";

async function readResponse(response: Response): Promise<ExamDraft> {
  if (!response.ok) {
    const body = (await response.json().catch(() => null)) as { detail?: string } | null;
    throw new Error(body?.detail || "Không thể hoàn tất yêu cầu.");
  }
  return response.json() as Promise<ExamDraft>;
}

async function readJson<T>(response: Response): Promise<T> {
  if (!response.ok) {
    const body = (await response.json().catch(() => null)) as { detail?: string } | null;
    throw new Error(body?.detail || "Không thể hoàn tất yêu cầu.");
  }
  return response.json() as Promise<T>;
}

export async function importExam(file: File): Promise<ExamDraft> {
  const form = new FormData();
  form.append("file", file);
  return readResponse(
    await fetch("/api/exams/import", {
      method: "POST",
      body: form,
    }),
  );
}

export async function getOverview(): Promise<Overview> {
  return readJson<Overview>(await fetch("/api/overview"));
}

export async function getClasses(): Promise<ClassroomRoster[]> {
  return readJson<ClassroomRoster[]>(await fetch("/api/classes"));
}

export async function saveClassroom(
  classroom: { id?: string; name: string; school_year: string; students: Array<{ name: string; student_code: string }> },
): Promise<ClassroomRoster> {
  const url = classroom.id ? `/api/classes/${encodeURIComponent(classroom.id)}` : "/api/classes";
  return readJson<ClassroomRoster>(
    await fetch(url, {
      method: classroom.id ? "PUT" : "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        name: classroom.name,
        school_year: classroom.school_year,
        students: classroom.students,
      }),
    }),
  );
}

export async function getExamDraft(draftId: string): Promise<ExamDraft> {
  return readResponse(await fetch(`/api/exams/${draftId}`));
}

export async function saveExam(draftId: string, exam: ParsedExam): Promise<ExamDraft> {
  return readResponse(
    await fetch(`/api/exams/${draftId}`, {
      method: "PUT",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ exam }),
    }),
  );
}

export async function publishDemoAssignment(draftId: string): Promise<Assignment> {
  return readJson<Assignment>(
    await fetch(`/api/exams/${draftId}/publish-demo`, {
      method: "POST",
    }),
  );
}

export async function publishAssignment(
  draftId: string,
  classId: string,
  durationMinutes: number,
  showScore = false,
  showAnswers = false,
): Promise<Assignment> {
  return readJson<Assignment>(
    await fetch(`/api/exams/${draftId}/publish`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        class_id: classId,
        duration_minutes: durationMinutes,
        show_score: showScore,
        show_answers: showAnswers,
      }),
    }),
  );
}

export async function updateAssignmentVisibility(
  code: string,
  showScore: boolean,
  showAnswers: boolean,
): Promise<Assignment> {
  return readJson<Assignment>(
    await fetch(`/api/assignments/${encodeURIComponent(code)}/visibility`, {
      method: "PUT",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ show_score: showScore, show_answers: showAnswers }),
    }),
  );
}

export async function getAssignment(code: string, studentId?: string): Promise<Assignment> {
  const params = studentId ? `?student_id=${encodeURIComponent(studentId)}` : "";
  return readJson<Assignment>(await fetch(`/api/assignments/${encodeURIComponent(code)}${params}`));
}

export async function autosaveSubmission(
  code: string,
  studentId: string,
  answers: Record<string, unknown>,
): Promise<SubmissionResult> {
  return readJson<SubmissionResult>(
    await fetch(`/api/assignments/${encodeURIComponent(code)}/submission`, {
      method: "PUT",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ student_id: studentId, answers }),
    }),
  );
}

export async function submitAssignment(
  code: string,
  studentId: string,
  answers: Record<string, unknown>,
): Promise<SubmissionResult> {
  return readJson<SubmissionResult>(
    await fetch(`/api/assignments/${encodeURIComponent(code)}/submit`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ student_id: studentId, answers }),
    }),
  );
}

export async function getAssignmentResults(code: string): Promise<AssignmentResults> {
  return readJson<AssignmentResults>(await fetch(`/api/assignments/${encodeURIComponent(code)}/results`));
}

export async function regradeAssignment(code: string): Promise<AssignmentResults> {
  return readJson<AssignmentResults>(
    await fetch(`/api/assignments/${encodeURIComponent(code)}/regrade`, {
      method: "POST",
    }),
  );
}

export async function getAssignmentAnalytics(code: string): Promise<AssignmentAnalytics> {
  return readJson<AssignmentAnalytics>(await fetch(`/api/assignments/${encodeURIComponent(code)}/analytics`));
}

export function assignmentCsvUrl(code: string): string {
  return `/api/assignments/${encodeURIComponent(code)}/export.csv`;
}

export function assignmentXlsxUrl(code: string): string {
  return `/api/assignments/${encodeURIComponent(code)}/export.xlsx`;
}
