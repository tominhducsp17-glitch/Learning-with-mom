export type TextBlock = {
  type: "text";
  text: string;
};

export type ImageBlock = {
  type: "image";
  asset_id: string;
  render_path: string;
  original_path: string;
  extension: string;
  status: string;
  extent_emu?: {
    cx: number;
    cy: number;
  };
  display_width_px?: number;
  display_height_px?: number;
};

export type ContentBlock = TextBlock | ImageBlock;

export type AssetMapEntry = Record<string, unknown> & {
  asset_id: string;
  render_path?: string;
  original_path?: string;
  extension?: string;
  status?: string;
  extent_emu?: {
    cx: number;
    cy: number;
  };
  display_width_px?: number;
  display_height_px?: number;
  occurrences?: Array<{
    extent_emu?: {
      cx: number;
      cy: number;
    };
    display_width_px?: number;
    display_height_px?: number;
  }>;
};

export type Question = {
  number: number;
  prompt_blocks: ContentBlock[];
  prompt_markup?: string;
  options?: Record<string, ContentBlock[]>;
  options_markup?: Record<string, string>;
  statements?: Record<string, ContentBlock[]>;
  statements_markup?: Record<string, string>;
  correct_answer?: string | Record<string, string> | null;
  score: number;
};

export type SectionType = "single_choice" | "true_false" | "short_answer";

export type ExamSection = {
  type: SectionType;
  title: string;
  questions: Question[];
};

export type ParserWarning = {
  code: string;
  severity: "warning" | "error";
  message: string;
  count?: number;
  section?: SectionType;
  question_number?: number;
};

export type ParsedExam = {
  schema_version: string;
  source_file: string;
  title: string;
  sections: ExamSection[];
  answer_keys: Record<string, unknown>;
  assets: Array<Record<string, unknown>>;
  assets_by_id?: Record<string, AssetMapEntry>;
  warnings: ParserWarning[];
};

export type ExamDraft = {
  id: string;
  title: string;
  source_filename: string;
  status: "draft";
  created_at: string;
  updated_at: string;
  exam: ParsedExam;
};

export type OcrSuggestionResponse = {
  asset_id: string;
  source_filename: string;
  replacement_token: string;
  suggestion: {
    latex: string;
    confidence: number;
    notes: string;
    needs_review: boolean;
    raw_text?: string;
  };
};

export type DraftSummary = {
  id: string;
  title: string;
  source_filename: string;
  status: "draft";
  created_at: string;
  updated_at: string;
  question_count: number;
  warning_count: number;
};

export type Student = {
  id: string;
  name: string;
  student_code: string;
  status: "not_started" | "in_progress" | "submitted";
};

export type Classroom = {
  id: string;
  name: string;
  school_year: string;
};

export type ClassroomRoster = Classroom & {
  created_at: string;
  students: Array<{
    id: string;
    name: string;
    student_code: string;
    created_at: string;
  }>;
};

export type Assignment = {
  id: string;
  code: string;
  status: "published";
  duration_minutes: number;
  show_score: boolean;
  show_answers: boolean;
  published_at: string;
  exam_id: string;
  draft_id: string;
  title: string;
  classroom: Classroom;
  students: Student[];
  exam: ParsedExam;
  submission?: {
    id: string;
    status: "in_progress" | "submitted";
    answers: Record<string, unknown>;
    created_at: string;
    updated_at: string;
    submitted_at: string | null;
    grade?: GradingResult;
  };
};

export type AssignmentSummary = {
  id: string;
  code: string;
  status: "published";
  duration_minutes: number;
  show_score: boolean;
  show_answers: boolean;
  published_at: string;
  title: string;
  draft_id: string;
  class_name: string;
  student_count: number;
  submitted_count: number;
  average_score: number | null;
  max_score: number | null;
};

export type Overview = {
  drafts: DraftSummary[];
  assignments: AssignmentSummary[];
};

export type GradingQuestionDetail = {
  section_type: SectionType;
  number: number;
  actual: unknown;
  expected: unknown;
  score: number;
  max_score: number;
  correct: boolean;
  items?: Record<string, {
    actual: unknown;
    expected: unknown;
    correct: boolean;
    score: number;
    max_score: number;
  }>;
};

export type GradingResult = {
  total_score: number;
  max_score: number;
  by_section: Record<string, { score: number; max_score: number }>;
  questions: GradingQuestionDetail[];
};

export type SubmissionResult = {
  id: string;
  assignment_code: string;
  student_id: string;
  status: "in_progress" | "submitted";
  answers: Record<string, unknown>;
  created_at: string;
  updated_at: string;
  submitted_at: string | null;
  grade: GradingResult | null;
};

export type ChatMessage = {
  role: "user" | "assistant";
  content: string;
};

export type StudentChatResponse = {
  answer: string;
  section_type: SectionType;
  question_number: number;
};

export type AssignmentResults = {
  assignment: {
    id: string;
    code: string;
    title: string;
    duration_minutes: number;
    show_score: boolean;
    show_answers: boolean;
    student_count: number;
    classroom: Classroom;
  };
  submissions: Array<{
    id: string;
    student: Student | null;
    status: "not_started" | "in_progress" | "submitted";
    answers: Record<string, unknown>;
    created_at: string | null;
    updated_at: string | null;
    submitted_at: string | null;
    graded_at: string | null;
    total_score: number | null;
    max_score: number | null;
    grading_detail: GradingResult | null;
  }>;
};

export type AssignmentAnalytics = {
  assignment: AssignmentResults["assignment"];
  summary: {
    student_count: number;
    submitted_count: number;
    average_score: number;
    max_score: number;
    highest_score: number;
    lowest_score: number;
  };
  distribution: Array<{ label: string; count: number }>;
  question_stats: Array<{
    section_type: SectionType;
    number: number;
    attempt_count: number;
    correct_count: number;
    wrong_count: number;
    correct_rate: number;
  }>;
  top_wrong_questions: Array<{
    section_type: SectionType;
    number: number;
    attempt_count: number;
    correct_count: number;
    wrong_count: number;
    correct_rate: number;
  }>;
  insight: string;
};
