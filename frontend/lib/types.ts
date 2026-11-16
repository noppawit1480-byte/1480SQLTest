// Mirrors the FastAPI responses (see docs/API.md).

export type Difficulty = "easy" | "medium" | "hard" | "expert";
export type Mode = "readonly" | "writable";

export interface User {
  id: number;
  email: string;
  display_name: string;
  role: "learner" | "admin";
  created_at: string | null;
}

export interface ColumnInfo {
  name: string;
  type: string;
}

export interface ResultSet {
  statement_index: number;
  command: string;
  columns: ColumnInfo[];
  rows: unknown[][];
  row_count: number;
  truncated: boolean;
}

export interface ExecError {
  message: string;
  sqlstate: string | null;
  detail: string | null;
  hint: string | null;
  line: number | null;
  column: number | null;
  statement_index: number | null;
  kind: "sql" | "timeout" | "limit" | "permission" | "internal";
}

export interface ExecutionResult {
  ok: boolean;
  result_sets: ResultSet[];
  exec_ms: number;
  statements: number;
  error: ExecError | null;
  notices: string[];
  new_achievements?: string[];
}

export interface TableColumn {
  name: string;
  type: string;
  nullable: boolean;
  default: string | null;
  is_pk: boolean;
  fk: string | null;
  comment: string | null;
}

export interface TableInfo {
  name: string;
  comment: string | null;
  row_estimate: number;
  columns: TableColumn[];
}

export interface DatabaseSummary {
  key: string;
  name: string;
  engine: string;
  description: string;
  tables: { name: string; rows: number }[];
}

export interface DatabaseDetail extends Omit<DatabaseSummary, "tables"> {
  mode: Mode;
  tables: TableInfo[];
  er_mermaid: string;
}

export interface CourseSummary {
  slug: string;
  title: string;
  level: string;
  description: string;
  lesson_count: number;
  completed: number;
  percent: number;
  first_lesson: string | null;
}

export type LessonStatus = "not_started" | "in_progress" | "completed";

export interface CourseDetail {
  slug: string;
  title: string;
  level: string;
  description: string;
  completed: number;
  percent: number;
  lessons: { slug: string; title: string; summary: string; position: number; status: LessonStatus; has_exercise: boolean }[];
}

export interface ExamplePreview {
  ok: boolean;
  exec_ms: number;
  commands: string[];
  columns?: ColumnInfo[];
  rows?: unknown[][];
  row_count?: number;
  truncated?: boolean;
  error?: { message: string; detail: string | null; sqlstate: string | null };
}

export interface LessonExample {
  title: string;
  sql: string;
  explain: string[];
  db: string;
  writable: boolean;
  result: ExamplePreview;
}

export interface NavLesson {
  slug: string;
  title: string;
  course_slug: string;
}

export interface LessonDetail {
  slug: string;
  title: string;
  summary: string;
  objectives: string[];
  content_md: string;
  examples: LessonExample[];
  common_mistakes: { title: string; wrong: string; right: string; why: string }[];
  sample_db: string | null;
  position: number;
  course: { slug: string; title: string; level: string; lessons: { slug: string; title: string }[] };
  prev: NavLesson | null;
  next: NavLesson | null;
  related: NavLesson[];
  exercises: { code: string; title: string; difficulty: Difficulty }[];
  status: LessonStatus;
  bookmarked: boolean;
  note: string;
}

export interface ExerciseSummary {
  code: string;
  title: string;
  difficulty: Difficulty;
  category: string;
  points: number;
  sample_db: string;
  check_type: "select" | "dml";
  status: "new" | "attempted" | "solved";
}

export interface ExerciseDetail {
  code: string;
  title: string;
  description_md: string;
  difficulty: Difficulty;
  category: string;
  points: number;
  sample_db: string;
  check_type: "select" | "dml";
  order_matters: boolean;
  expected: { columns: ColumnInfo[]; rows: unknown[][]; row_count: number };
  hints: string[];
  lesson: NavLesson | null;
  project: { slug: string; title: string; task_no: number; task_count: number } | null;
  prev: string | null;
  next: string | null;
  status: "new" | "attempted" | "solved";
  attempts: number;
}

export interface SubmitResult {
  correct: boolean;
  reason_code: string;
  message: string;
  details: Record<string, unknown>;
  points_awarded: number;
  execution: ExecutionResult;
  actual: { columns: ColumnInfo[]; rows: unknown[][] } | null;
  expected: { columns: ColumnInfo[]; rows: unknown[][]; row_count: number };
  explanation_md: string;
  solution_sql: string;
  new_achievements: string[];
}

export interface Achievement {
  key: string;
  title: string;
  description: string;
  icon: string;
  earned_at: string | null;
}

export interface Dashboard {
  lessons: { completed: number; total: number };
  exercises: { solved: number; total: number };
  projects: { completed: number; total: number; tasks_solved: number; tasks_total: number };
  submissions: { total: number; correct: number; accuracy: number | null };
  streak: number;
  learning_seconds: number;
  level: { name: string; points: number; current_threshold: number; next_name: string | null; next_threshold: number | null };
  courses: { slug: string; title: string; level: string; total: number; completed: number; percent: number }[];
  skills: { category: string; solved: number; total: number; percent: number }[];
  recent_exercises: { code: string; title: string; difficulty: Difficulty; is_correct: boolean; at: string }[];
  current_lesson: NavLesson | null;
  activity: { date: string; submissions: number; correct: number; minutes: number }[];
  achievements: Achievement[];
}

export interface HistoryItem {
  id: number;
  db_key: string;
  mode: Mode;
  sql: string;
  success: boolean;
  row_count: number;
  exec_ms: number;
  created_at: string;
}

export interface SavedQuery {
  id: number;
  title: string;
  db_key: string;
  sql: string;
  updated_at: string;
}

export interface SyntaxIssue {
  message: string;
  line: number;
  column: number;
  end_column: number;
}

export interface ProjectSummary {
  slug: string;
  title: string;
  role: string;
  summary: string;
  sample_db: string;
  difficulty: Difficulty;
  tasks: number;
  solved: number;
  completed: boolean;
}

export interface ProjectDetail {
  slug: string;
  title: string;
  role: string;
  summary: string;
  brief_md: string;
  deliverables: string[];
  sample_db: string;
  difficulty: Difficulty;
  tasks: { code: string; title: string; difficulty: Difficulty; category: string; points: number; status: "new" | "attempted" | "solved" }[];
  solved: number;
  completed: boolean;
  points_total: number;
  points_earned: number;
}

export interface AssistantFinding {
  code: string;
  severity: "info" | "warning" | "danger" | "perf";
  title: string;
  body_md: string;
  suggestion_sql: string | null;
}

export interface AssistantAnswer {
  mode: string;
  source: "rules" | "rules+ai";
  summary: string;
  sections: { title: string; body_md: string; sql: string | null }[];
  findings: AssistantFinding[];
  plan: { depth: number; node: string; relation: string | null; alias: string | null; index: string | null; rows: number; cost: number; filter: string | null }[] | null;
  ai_md: string | null;
}

export interface AssistantStatus {
  ai_available: boolean;
  provider: string;
  model: string;
}

export interface GeneratedPractice {
  id: number;
  db_key: string;
  topic: string;
  title: string;
  description_md: string;
  hints: string[];
  order_matters: boolean;
  solved: boolean;
  expected: { columns: ColumnInfo[]; rows: unknown[][]; row_count: number };
  created_at: string | null;
}
