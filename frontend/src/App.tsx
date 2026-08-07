import { ChangeEvent, useEffect, useMemo, useRef, useState } from "react";
import type { CSSProperties, ReactNode, RefObject } from "react";
import {
  AlertTriangle,
  BarChart3,
  BookOpen,
  Check,
  ChevronDown,
  ChevronRight,
  Clock,
  Download,
  Eye,
  FileText,
  Flower2,
  GraduationCap,
  ImageOff,
  Link,
  LoaderCircle,
  Pencil,
  RotateCcw,
  Save,
  Send,
  Sigma,
  Upload,
  Users,
  X,
} from "lucide-react";
import {
  autosaveSubmission,
  assignmentCsvUrl,
  assignmentXlsxUrl,
  getAssignment,
  getAssignmentAnalytics,
  getClasses,
  getExamDraft,
  getOverview,
  getAssignmentResults,
  importExam,
  publishAssignment,
  regradeAssignment,
  saveExam,
  saveClassroom,
  submitAssignment,
  updateAssignmentVisibility,
} from "./api";
import type {
  Assignment,
  AssignmentAnalytics,
  AssignmentResults,
  ClassroomRoster,
  ContentBlock,
  DraftSummary,
  ExamDraft,
  GradingQuestionDetail,
  GradingResult,
  Overview,
  ParsedExam,
  Question,
  SectionType,
} from "./types";

const SECTION_LABELS: Record<SectionType, string> = {
  single_choice: "PHẦN I",
  true_false: "PHẦN II",
  short_answer: "PHẦN III",
};

const SECTION_NAMES: Record<SectionType, string> = {
  single_choice: "Trắc nghiệm A/B/C/D",
  true_false: "Đúng/Sai",
  short_answer: "Trả lời ngắn",
};

function App() {
  const [studentCode, setStudentCode] = useState(() => studentCodeFromHash());
  const [draft, setDraft] = useState<ExamDraft | null>(null);
  const [assignment, setAssignment] = useState<Assignment | null>(null);
  const [assignmentResults, setAssignmentResults] = useState<AssignmentResults | null>(null);
  const [assignmentAnalytics, setAssignmentAnalytics] = useState<AssignmentAnalytics | null>(null);
  const [overview, setOverview] = useState<Overview | null>(null);
  const [classrooms, setClassrooms] = useState<ClassroomRoster[]>([]);
  const [selectedClassId, setSelectedClassId] = useState("");
  const [durationMinutes, setDurationMinutes] = useState(45);
  const [showScoreToStudents, setShowScoreToStudents] = useState(false);
  const [showAnswersToStudents, setShowAnswersToStudents] = useState(false);
  const [showClassManager, setShowClassManager] = useState(false);
  const [joinCode, setJoinCode] = useState("");
  const [busy, setBusy] = useState(false);
  const [saving, setSaving] = useState(false);
  const [publishing, setPublishing] = useState(false);
  const [dirty, setDirty] = useState(false);
  const [error, setError] = useState("");
  const [activeSection, setActiveSection] = useState<SectionType>("single_choice");
  const [activeQuestion, setActiveQuestion] = useState(1);
  const [editMode, setEditMode] = useState(false);
  const [showMarkupPanel, setShowMarkupPanel] = useState(false);
  const [showWarnings, setShowWarnings] = useState(true);
  const inputRef = useRef<HTMLInputElement>(null);

  const section = draft?.exam.sections.find((item) => item.type === activeSection);
  const question = section?.questions.find((item) => item.number === activeQuestion) ?? section?.questions[0];

  useEffect(() => {
    const syncRoute = () => setStudentCode(studentCodeFromHash());
    window.addEventListener("hashchange", syncRoute);
    return () => window.removeEventListener("hashchange", syncRoute);
  }, []);

  useEffect(() => {
    void refreshOverview();
    void refreshClasses();
  }, []);

  useEffect(() => {
    if (!assignment?.code) return;
    const code = assignment.code;
    const intervalId = window.setInterval(() => {
      Promise.all([
        getAssignmentResults(code),
        getAssignmentAnalytics(code),
      ])
        .then(([nextResults, nextAnalytics]) => {
          setAssignmentResults(nextResults);
          setAssignmentAnalytics(nextAnalytics);
        })
        .catch(() => {
          // Keep the current dashboard visible if a background refresh fails.
        });
    }, 30000);
    return () => window.clearInterval(intervalId);
  }, [assignment?.code]);

  const totalQuestions = useMemo(
    () => draft?.exam.sections.reduce((total, item) => total + item.questions.length, 0) ?? 0,
    [draft],
  );
  const selectedClassroom = classrooms.find((classroom) => classroom.id === selectedClassId) ?? null;
  const assignmentHref = assignment ? `${window.location.origin}/#student/${assignment.code}` : "";

  async function handleFile(file?: File) {
    if (!file) return;
    setBusy(true);
    setError("");
    try {
      const imported = await importExam(file);
      setDraft(imported);
      setAssignment(null);
      setAssignmentResults(null);
      setAssignmentAnalytics(null);
      setActiveSection("single_choice");
      setActiveQuestion(imported.exam.sections[0]?.questions[0]?.number ?? 1);
      setDirty(false);
      void refreshOverview();
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : "Không thể nhập đề.");
    } finally {
      setBusy(false);
      if (inputRef.current) inputRef.current.value = "";
    }
  }

  function updateExam(mutator: (exam: ParsedExam) => void) {
    setDraft((current) => {
      if (!current) return current;
      const next = structuredClone(current);
      mutator(next.exam);
      next.title = next.exam.title;
      return next;
    });
    setDirty(true);
  }

  function updateQuestion(mutator: (item: Question) => void) {
    updateExam((exam) => {
      const targetSection = exam.sections.find((item) => item.type === activeSection);
      const target = targetSection?.questions.find((item) => item.number === question?.number);
      if (target) mutator(target);
    });
  }

  async function handleSave() {
    if (!draft) return;
    setSaving(true);
    setError("");
    try {
      const saved = await saveExam(draft.id, draft.exam);
      setDraft(saved);
      setDirty(false);
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : "Không thể lưu bản nháp.");
    } finally {
      setSaving(false);
    }
  }

  async function handlePublishDemo() {
    if (!draft) return;
    if (!selectedClassId) {
      setError("Hãy tạo hoặc chọn một lớp trước khi giao bài.");
      setShowClassManager(true);
      return;
    }
    setPublishing(true);
    setError("");
    try {
      const published = await publishAssignment(
        draft.id,
        selectedClassId,
        durationMinutes,
        showScoreToStudents,
        showAnswersToStudents,
      );
      setAssignment(published);
      setAssignmentResults(await getAssignmentResults(published.code));
      setAssignmentAnalytics(await getAssignmentAnalytics(published.code));
      void refreshOverview();
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : "Không thể giao đề.");
    } finally {
      setPublishing(false);
    }
  }

  async function refreshOverview() {
    try {
      setOverview(await getOverview());
    } catch {
      setOverview(null);
    }
  }

  async function refreshClasses() {
    try {
      const loadedClasses = await getClasses();
      setClassrooms(loadedClasses);
      setSelectedClassId((current) => current || loadedClasses[0]?.id || "");
      if (loadedClasses.length === 0) setShowClassManager(true);
    } catch {
      setClassrooms([]);
    }
  }

  async function handleSaveClassroom(payload: {
    id?: string;
    name: string;
    school_year: string;
    students: Array<{ name: string; student_code: string }>;
  }) {
    setSaving(true);
    setError("");
    try {
      const savedClassroom = await saveClassroom(payload);
      await refreshClasses();
      setSelectedClassId(savedClassroom.id);
      setShowClassManager(false);
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : "Không thể lưu lớp.");
    } finally {
      setSaving(false);
    }
  }

  async function openDraft(draftId: string) {
    setBusy(true);
    setError("");
    try {
      const loaded = await getExamDraft(draftId);
      setDraft(loaded);
      setAssignment(null);
      setAssignmentResults(null);
      setAssignmentAnalytics(null);
      setActiveSection("single_choice");
      setActiveQuestion(loaded.exam.sections[0]?.questions[0]?.number ?? 1);
      setDirty(false);
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : "Không thể mở bản nháp.");
    } finally {
      setBusy(false);
    }
  }

  function openStudentCode() {
    const code = joinCode.trim().toUpperCase();
    if (!code) return;
    window.location.hash = `student/${code}`;
    setStudentCode(code);
  }

  async function openTeacherAssignment(code: string) {
    const normalizedCode = code.trim().toUpperCase();
    if (!normalizedCode) return;
    setBusy(true);
    setError("");
    try {
      const loadedAssignment = await getAssignment(normalizedCode);
      const [loadedDraft, loadedResults, loadedAnalytics] = await Promise.all([
        getExamDraft(loadedAssignment.draft_id),
        getAssignmentResults(normalizedCode),
        getAssignmentAnalytics(normalizedCode),
      ]);
      setDraft(loadedDraft);
      setAssignment(loadedAssignment);
      setAssignmentResults(loadedResults);
      setAssignmentAnalytics(loadedAnalytics);
      setSelectedClassId(loadedAssignment.classroom.id);
      setDurationMinutes(loadedAssignment.duration_minutes || 45);
      setShowScoreToStudents(loadedAssignment.show_score);
      setShowAnswersToStudents(loadedAssignment.show_answers);
      setActiveSection("single_choice");
      setActiveQuestion(loadedDraft.exam.sections[0]?.questions[0]?.number ?? 1);
      setDirty(false);
      setEditMode(false);
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : "Khong the mo dashboard bai da giao.");
    } finally {
      setBusy(false);
    }
  }

  function goHome() {
    if (dirty && !window.confirm("Bản nháp chưa lưu. Bạn vẫn muốn quay về trang tạo đề?")) {
      return;
    }
    window.location.hash = "";
    setStudentCode("");
    setDraft(null);
    setAssignment(null);
    setAssignmentResults(null);
    setAssignmentAnalytics(null);
    setError("");
    setDirty(false);
    setEditMode(false);
    void refreshOverview();
  }

  async function refreshResults() {
    if (!assignment) return;
    setSaving(true);
    setError("");
    try {
      setAssignmentResults(await getAssignmentResults(assignment.code));
      setAssignmentAnalytics(await getAssignmentAnalytics(assignment.code));
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : "Không thể tải bảng điểm.");
    } finally {
      setSaving(false);
    }
  }

  async function handleRegrade() {
    if (!assignment) return;
    setSaving(true);
    setError("");
    try {
      setAssignmentResults(await regradeAssignment(assignment.code));
      setAssignmentAnalytics(await getAssignmentAnalytics(assignment.code));
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : "Không thể chấm lại.");
    } finally {
      setSaving(false);
    }
  }

  async function handleVisibilityChange(nextShowScore: boolean, nextShowAnswers: boolean) {
    if (!assignment) {
      setShowScoreToStudents(nextShowScore);
      setShowAnswersToStudents(nextShowAnswers);
      return;
    }
    setSaving(true);
    setError("");
    try {
      const updated = await updateAssignmentVisibility(assignment.code, nextShowScore, nextShowAnswers);
      setAssignment(updated);
      setShowScoreToStudents(updated.show_score);
      setShowAnswersToStudents(updated.show_answers);
      setAssignmentResults(await getAssignmentResults(updated.code));
      setAssignmentAnalytics(await getAssignmentAnalytics(updated.code));
      void refreshOverview();
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : "Không thể cập nhật quyền xem kết quả.");
    } finally {
      setSaving(false);
    }
  }

  if (studentCode) {
    return <StudentRunner code={studentCode} onBack={() => {
      window.location.hash = "";
      setStudentCode("");
    }} />;
  }

  if (!draft) {
    return (
      <HomeScreen
        busy={busy}
        error={error}
        inputRef={inputRef}
        overview={overview}
        joinCode={joinCode}
        onJoinCodeChange={setJoinCode}
        onJoin={openStudentCode}
        onFile={handleFile}
        onOpenDraft={(draftId) => void openDraft(draftId)}
        onOpenTeacherAssignment={(code) => void openTeacherAssignment(code)}
        onOpenStudentAssignment={(code) => {
          window.location.hash = `student/${code}`;
          setStudentCode(code);
        }}
      />
    );
  }

  if (!draft) {
    return (
      <main className="import-shell">
        <section className="import-panel" aria-labelledby="import-title">
          <div className="brand-line">
            <span className="brand-mark">T</span>
            <span>Học cùng cô Tuyết</span>
          </div>
          <div className="import-heading">
            <p className="eyebrow">Nhập đề thi</p>
            <h1 id="import-title">Chọn file Word để bắt đầu duyệt đề</h1>
            <p>Hỗ trợ cấu trúc Azota gồm trắc nghiệm, đúng/sai và trả lời ngắn.</p>
          </div>
          <label className={`drop-zone ${busy ? "is-busy" : ""}`}>
            <input
              ref={inputRef}
              type="file"
              accept=".docx,application/vnd.openxmlformats-officedocument.wordprocessingml.document"
              disabled={busy}
              onChange={(event) => void handleFile(event.target.files?.[0])}
            />
            {busy ? <LoaderCircle className="spin" size={30} /> : <Upload size={30} />}
            <strong>{busy ? "Đang đọc câu hỏi và đáp án..." : "Chọn file .docx"}</strong>
            <span>Tối đa 25 MB</span>
          </label>
          {error && <div className="error-banner">{error}</div>}
          <div className="import-foot">
            <FileText size={18} />
            <span>File gốc và các công thức được lưu cùng bản nháp.</span>
          </div>
        </section>
      </main>
    );
  }

  return (
    <div className="app-shell">
      <header className="topbar">
        <div className="topbar-title">
          <button
            className="brand-mark brand-home"
            type="button"
            title="Về trang tạo đề"
            aria-label="Về trang tạo đề"
            onClick={goHome}
          >
            T
          </button>
          <div>
            <input
              className="title-input"
              value={draft.exam.title}
              aria-label="Tên đề thi"
              onChange={(event) => updateExam((exam) => void (exam.title = event.target.value))}
            />
            <div className="source-line">{draft.source_filename} · {totalQuestions} câu</div>
          </div>
        </div>
        <div className="topbar-actions">
          <button className="icon-button" title="Nhập file khác" aria-label="Nhập file khác" onClick={() => inputRef.current?.click()}>
            <RotateCcw size={18} />
          </button>
          <input
            ref={inputRef}
            className="visually-hidden"
            type="file"
            accept=".docx"
            onChange={(event) => void handleFile(event.target.files?.[0])}
          />
          <button
            className={`icon-button ${editMode ? "is-active" : ""}`}
            title="Bật/tắt sửa nội dung"
            aria-label="Bật/tắt sửa nội dung"
            aria-pressed={editMode}
            onClick={() => setEditMode((value) => !value)}
          >
            <Pencil size={18} />
          </button>
          <button
            className={`icon-button ${showMarkupPanel ? "is-active" : ""}`}
            title="Xem markup nội dung"
            aria-label="Xem markup nội dung"
            aria-pressed={showMarkupPanel}
            onClick={() => setShowMarkupPanel((value) => !value)}
          >
            <Sigma size={18} />
          </button>
          <button className="primary-button" disabled={!dirty || saving} onClick={() => void handleSave()}>
            {saving ? <LoaderCircle className="spin" size={18} /> : dirty ? <Save size={18} /> : <Check size={18} />}
            <span>{saving ? "Đang lưu" : dirty ? "Lưu bản nháp" : "Đã lưu"}</span>
          </button>
          <div className="topbar-duration" title="Thời gian làm bài">
            <Clock size={17} />
            <input
              aria-label="Thời gian làm bài, phút"
              type="number"
              min="1"
              max="300"
              value={durationMinutes}
              onChange={(event) => {
                const value = Number(event.target.value);
                setDurationMinutes(Number.isFinite(value) ? Math.max(1, Math.min(300, value)) : 45);
              }}
            />
            <span>phút</span>
          </div>
          <button className="primary-button" disabled={dirty || publishing || !selectedClassId} onClick={() => void handlePublishDemo()}>
            {publishing ? <LoaderCircle className="spin" size={18} /> : <Users size={18} />}
            <span>{publishing ? "Đang giao" : "Giao bài"}</span>
          </button>
          <button className="secondary-button" onClick={() => setShowClassManager((value) => !value)}>
            <Users size={18} />
            <span>Lớp học</span>
          </button>
        </div>
      </header>

      <section className="publish-config">
        <div className="config-field">
          <label htmlFor="class-select">Lớp nhận đề</label>
          <select
            id="class-select"
            value={selectedClassId}
            onChange={(event) => setSelectedClassId(event.target.value)}
          >
            {classrooms.length === 0 && <option value="">Chưa có lớp</option>}
            {classrooms.map((classroom) => (
              <option key={classroom.id} value={classroom.id}>
                {classroom.name} · {classroom.students.length} học sinh
              </option>
            ))}
          </select>
        </div>
        <div className="config-field duration-field">
          <label htmlFor="duration-minutes">Thời gian</label>
          <div className="number-field">
            <input
              id="duration-minutes"
              type="number"
              min="1"
              max="300"
              value={durationMinutes}
              onChange={(event) => {
                const value = Number(event.target.value);
                setDurationMinutes(Number.isFinite(value) ? Math.max(1, Math.min(300, value)) : 45);
              }}
            />
            <span>phút</span>
          </div>
        </div>
        <label className="toggle-field">
          <input
            type="checkbox"
            checked={showScoreToStudents}
            onChange={(event) => void handleVisibilityChange(event.target.checked, event.target.checked ? showAnswersToStudents : false)}
          />
          <span>Xem điểm</span>
        </label>
        <label className="toggle-field">
          <input
            type="checkbox"
            checked={showAnswersToStudents}
            disabled={!showScoreToStudents}
            onChange={(event) => void handleVisibilityChange(showScoreToStudents, event.target.checked)}
          />
          <span>Xem đáp án</span>
        </label>
        <div className="config-summary">
          <Clock size={18} />
          <span>{selectedClassroom ? `${selectedClassroom.name} · ${selectedClassroom.students.length} học sinh` : "Tạo lớp trước khi giao đề"}</span>
        </div>
        <button className="primary-button" disabled={dirty || publishing || !selectedClassId} onClick={() => void handlePublishDemo()}>
          {publishing ? <LoaderCircle className="spin" size={18} /> : <Users size={18} />}
          <span>{publishing ? "Đang giao" : "Giao bài"}</span>
        </button>
      </section>

      {showClassManager && (
        <ClassManager
          classrooms={classrooms}
          selectedClassId={selectedClassId}
          saving={saving}
          onSelect={setSelectedClassId}
          onSave={(payload) => void handleSaveClassroom(payload)}
          onClose={() => setShowClassManager(false)}
        />
      )}

      {error && <div className="error-banner workspace-error">{error}</div>}

      {assignment && (
        <section className="publish-strip">
          <div>
            <Users size={18} />
            <strong>Lớp {assignment.classroom.name}</strong>
            <span>{assignment.students.length} học sinh · {assignment.duration_minutes} phút</span>
          </div>
          <div className="publish-visibility">
            <label>
              <input
                type="checkbox"
                checked={assignment.show_score}
                onChange={(event) => void handleVisibilityChange(event.target.checked, event.target.checked ? assignment.show_answers : false)}
              />
              <span>Công bố điểm</span>
            </label>
            <label>
              <input
                type="checkbox"
                checked={assignment.show_answers}
                disabled={!assignment.show_score}
                onChange={(event) => void handleVisibilityChange(assignment.show_score, event.target.checked)}
              />
              <span>Công bố đáp án</span>
            </label>
          </div>
          <div className="publish-link">
            <Link size={17} />
            <a href={`#student/${assignment.code}`}>{assignmentHref}</a>
          </div>
          <div className="publish-actions">
            <button className="icon-button" title="Tải kết quả" aria-label="Tải kết quả" onClick={() => void refreshResults()}>
              <RotateCcw size={16} />
            </button>
            <button className="icon-button" title="Chấm lại" aria-label="Chấm lại" onClick={() => void handleRegrade()}>
              <Sigma size={16} />
            </button>
            <a className="icon-button" title="Xuất CSV" aria-label="Xuất CSV" href={assignmentCsvUrl(assignment.code)}>
              <Download size={16} />
            </a>
          </div>
          <span className="assignment-code">{assignment.code}</span>
        </section>
      )}

      {assignmentResults && <TeacherResults results={assignmentResults} />}
      {assignmentAnalytics && <TeacherAnalytics analytics={assignmentAnalytics} />}

      <nav className="section-tabs" aria-label="Các phần của đề">
        {draft.exam.sections.map((item) => (
          <button
            key={item.type}
            className={item.type === activeSection ? "is-active" : ""}
            onClick={() => {
              setActiveSection(item.type);
              setActiveQuestion(item.questions[0]?.number ?? 1);
            }}
          >
            <strong>{SECTION_LABELS[item.type]}</strong>
            <span>{item.questions.length} câu</span>
          </button>
        ))}
      </nav>

      {draft.exam.warnings.length > 0 && (
        <section className="warning-strip">
          <button className="warning-summary" onClick={() => setShowWarnings((value) => !value)} aria-expanded={showWarnings}>
            <AlertTriangle size={19} />
            <span>{draft.exam.warnings.length} cảnh báo parser</span>
            <ChevronDown className={showWarnings ? "is-open" : ""} size={18} />
          </button>
          {showWarnings && (
            <div className="warning-list">
              {draft.exam.warnings.map((warning, index) => (
                <div key={`${warning.code}-${index}`}>
                  <strong>{warning.code}</strong>
                  <span>{warning.message}</span>
                </div>
              ))}
            </div>
          )}
        </section>
      )}

      <main className="review-workspace">
        <aside className="question-nav" aria-label="Danh sách câu hỏi">
          <div className="aside-heading">
            <strong>{SECTION_LABELS[activeSection]}</strong>
            <span>{SECTION_NAMES[activeSection]}</span>
          </div>
          <div className="question-grid">
            {section?.questions.map((item) => (
              <button
                key={item.number}
                className={item.number === question?.number ? "is-active" : ""}
                aria-label={`Câu ${item.number}`}
                onClick={() => setActiveQuestion(item.number)}
              >
                {item.number}
              </button>
            ))}
          </div>
        </aside>

        <section className="question-stage">
          {question && (
            <>
              <QuestionContent
                sectionType={activeSection}
                question={question}
                editMode={editMode}
                onChange={updateQuestion}
              />
              {showMarkupPanel && <MarkupPanel sectionType={activeSection} question={question} />}
            </>
          )}
        </section>

        <aside className="answer-inspector">
          {question && (
            <AnswerEditor sectionType={activeSection} question={question} onChange={updateQuestion} />
          )}
        </aside>
      </main>
    </div>
  );
}

function ClassManager({
  classrooms,
  selectedClassId,
  saving,
  onSelect,
  onSave,
  onClose,
}: {
  classrooms: ClassroomRoster[];
  selectedClassId: string;
  saving: boolean;
  onSelect: (classId: string) => void;
  onSave: (payload: {
    id?: string;
    name: string;
    school_year: string;
    students: Array<{ name: string; student_code: string }>;
  }) => void;
  onClose: () => void;
}) {
  const [editingId, setEditingId] = useState("");
  const [name, setName] = useState("12A1");
  const [schoolYear, setSchoolYear] = useState("2026-2027");
  const [rosterText, setRosterText] = useState("HS001 - Nguyễn An\nHS002 - Trần Bình\nHS003 - Lê Chi");

  useEffect(() => {
    const classroom = classrooms.find((item) => item.id === selectedClassId) ?? classrooms[0];
    if (!classroom) return;
    setEditingId(classroom.id);
    setName(classroom.name);
    setSchoolYear(classroom.school_year);
    setRosterText(
      classroom.students
        .map((student) => `${student.student_code} - ${student.name}`)
        .join("\n"),
    );
  }, [classrooms, selectedClassId]);

  function startNewClass() {
    setEditingId("");
    setName("");
    setSchoolYear("2026-2027");
    setRosterText("");
  }

  const parsedStudents = parseRosterText(rosterText);

  return (
    <section className="class-manager">
      <div className="class-manager-head">
        <div>
          <strong>Quản lý lớp học</strong>
          <span>Nhập mỗi học sinh một dòng, ví dụ: HS001 - Nguyễn An</span>
        </div>
        <div className="class-manager-actions">
          <button className="secondary-button" type="button" onClick={startNewClass}>Lớp mới</button>
          <button className="icon-button" type="button" aria-label="Đóng quản lý lớp" title="Đóng" onClick={onClose}>
            <ChevronDown size={18} />
          </button>
        </div>
      </div>

      <div className="class-manager-grid">
        <div className="class-list">
          {classrooms.length === 0 && <div className="empty-card">Chưa có lớp nào.</div>}
          {classrooms.map((classroom) => (
            <button
              key={classroom.id}
              className={classroom.id === editingId ? "is-active" : ""}
              onClick={() => {
                onSelect(classroom.id);
                setEditingId(classroom.id);
              }}
            >
              <strong>{classroom.name}</strong>
              <span>{classroom.students.length} học sinh · {classroom.school_year}</span>
            </button>
          ))}
        </div>

        <div className="class-form">
          <div className="form-row two">
            <label>
              <span>Tên lớp</span>
              <input className="text-input" value={name} onChange={(event) => setName(event.target.value)} />
            </label>
            <label>
              <span>Năm học</span>
              <input className="text-input" value={schoolYear} onChange={(event) => setSchoolYear(event.target.value)} />
            </label>
          </div>
          <label className="roster-field">
            <span>Danh sách học sinh</span>
            <textarea
              value={rosterText}
              rows={8}
              onChange={(event) => setRosterText(event.target.value)}
            />
          </label>
          <div className="class-form-foot">
            <span>{parsedStudents.length} học sinh sẽ được lưu</span>
            <button
              className="primary-button"
              disabled={saving || !name.trim() || parsedStudents.length === 0}
              onClick={() => onSave({
                id: editingId || undefined,
                name,
                school_year: schoolYear,
                students: parsedStudents,
              })}
            >
              {saving ? <LoaderCircle className="spin" size={18} /> : <Save size={18} />}
              <span>{saving ? "Đang lưu" : "Lưu lớp"}</span>
            </button>
          </div>
        </div>
      </div>
    </section>
  );
}

function parseRosterText(text: string): Array<{ name: string; student_code: string }> {
  return text
    .split(/\r?\n/)
    .map((line, index) => {
      const trimmed = line.trim();
      if (!trimmed) return null;
      const match = trimmed.match(/^([A-Za-z0-9_-]+)\s*[-–]\s*(.+)$/);
      if (match) {
        return { student_code: match[1].toUpperCase(), name: match[2].trim() };
      }
      return { student_code: `HS${String(index + 1).padStart(3, "0")}`, name: trimmed };
    })
    .filter((student): student is { name: string; student_code: string } => Boolean(student?.name));
}

type HomeScreenProps = {
  busy: boolean;
  error: string;
  inputRef: RefObject<HTMLInputElement | null>;
  overview: Overview | null;
  joinCode: string;
  onJoinCodeChange: (value: string) => void;
  onJoin: () => void;
  onFile: (file?: File) => void;
  onOpenDraft: (draftId: string) => void;
  onOpenTeacherAssignment: (code: string) => void;
  onOpenStudentAssignment: (code: string) => void;
};

function HomeScreen({
  busy,
  error,
  inputRef,
  overview,
  joinCode,
  onJoinCodeChange,
  onJoin,
  onFile,
  onOpenDraft,
  onOpenTeacherAssignment,
  onOpenStudentAssignment,
}: HomeScreenProps) {
  const drafts = overview?.drafts ?? [];
  const assignments = overview?.assignments ?? [];
  const [homeRole, setHomeRole] = useState<"teacher" | "student">("teacher");
  const isTeacher = homeRole === "teacher";

  function openTypedCode() {
    if (isTeacher) {
      onOpenTeacherAssignment(joinCode);
      return;
    }
    onJoin();
  }

  return (
    <main className="home-shell">
      <header className="home-top">
        <div className="home-brand">
          <span className="brand-mark big"><Flower2 size={32} /></span>
          <div>
            <strong>Học cùng cô Tuyết</strong>
            <span>MathExam spark</span>
          </div>
        </div>
        <div className="role-switch" aria-label="Vai trò">
          <button
            type="button"
            className={isTeacher ? "is-active" : ""}
            onClick={() => setHomeRole("teacher")}
          >
            <GraduationCap size={24} /> Giáo viên
          </button>
          <button
            type="button"
            className={!isTeacher ? "is-active" : ""}
            onClick={() => setHomeRole("student")}
          >
            <BookOpen size={24} /> Học sinh
          </button>
        </div>
        <div className="teacher-chip">Cô Tuyết</div>
      </header>

      <section className="hero-board">
        <div className="hero-copy">
          <p className="eyebrow">{isTeacher ? "Không gian giáo viên" : "Không gian học sinh"}</p>
          <h1>{isTeacher ? "Biến đề Word thành bài kiểm tra online." : "Vào bài kiểm tra thật nhanh."}</h1>
          <p>{isTeacher ? "Upload file Azota, kiểm tra công thức, giao cho lớp và xem điểm ngay trong một luồng làm việc gọn gàng." : "Nhập mã bài hoặc chọn bài đã giao để bắt đầu làm bài trên máy tính."}</p>
        </div>
        <div className="hero-stack" aria-hidden="true">
          <span className="hero-card pdf">DOCX</span>
          <span className="hero-card brain"><Sigma size={42} /></span>
          <span className="hero-card ai">AI</span>
        </div>
      </section>

      <section className={`home-grid ${isTeacher ? "" : "student-home-grid"}`}>
        {isTeacher ? (
          <article className="home-panel upload-panel">
            <div className="panel-heading">
              <span className="panel-icon lavender"><Upload size={32} /></span>
              <div>
                <span>Bước 01</span>
                <h2>Tải đề Word</h2>
              </div>
            </div>
            <label className={`friendly-drop ${busy ? "is-busy" : ""}`}>
              <input
                ref={inputRef}
                type="file"
                accept=".docx,application/vnd.openxmlformats-officedocument.wordprocessingml.document"
                disabled={busy}
                onChange={(event) => onFile(event.target.files?.[0])}
              />
              {busy ? <LoaderCircle className="spin" size={42} /> : <FileText size={46} />}
              <strong>{busy ? "Đang đọc đề..." : "Thả file .docx vào đây"}</strong>
              <span>Parser sẽ giữ công thức/ảnh và tách 3 phần đề.</span>
            </label>
            {error && <div className="error-banner">{error}</div>}
          </article>
        ) : (
          <article className="home-panel student-join-panel">
            <div className="panel-heading">
              <span className="panel-icon lavender"><BookOpen size={32} /></span>
              <div>
                <span>Học sinh</span>
                <h2>Vào làm bài</h2>
              </div>
            </div>
            <div className="student-mode-note">
              Chọn bài được giao hoặc nhập mã bài do giáo viên gửi.
            </div>
          </article>
        )}

        <article className="home-panel">
          <div className="panel-heading">
            <span className="panel-icon sunny">{isTeacher ? <BarChart3 size={32} /> : <Send size={32} />}</span>
            <div>
              <span>Bước 02</span>
              <h2>{isTeacher ? "Xem dashboard lớp" : "Mở bài đã giao"}</h2>
            </div>
          </div>
          <div className="code-join">
            <input
              value={joinCode}
              placeholder={isTeacher ? "Nhập mã bài để xem kết quả" : "Nhập mã bài của học sinh"}
              onChange={(event) => onJoinCodeChange(event.target.value.toUpperCase())}
              onKeyDown={(event) => {
                if (event.key === "Enter") openTypedCode();
              }}
            />
            <button className="send-button" aria-label={isTeacher ? "Mở dashboard" : "Vào bài"} onClick={openTypedCode}>
              <Send size={24} fill="currentColor" />
            </button>
          </div>
          <AssignmentShelf
            assignments={assignments}
            actionLabel={isTeacher ? "Kết quả" : "Làm bài"}
            onOpenAssignment={isTeacher ? onOpenTeacherAssignment : onOpenStudentAssignment}
          />
        </article>
      </section>

      {isTeacher && (
        <section className="library-band">
          <div className="library-heading">
            <span className="panel-icon mint"><FileText size={28} /></span>
            <div>
              <span>Thư viện đề</span>
              <h2>Bản nháp gần đây</h2>
            </div>
          </div>
          <DraftShelf drafts={drafts} onOpenDraft={onOpenDraft} />
        </section>
      )}
    </main>
  );
}

function AssignmentShelf({
  assignments,
  actionLabel,
  onOpenAssignment,
}: {
  assignments: Overview["assignments"];
  actionLabel: string;
  onOpenAssignment: (code: string) => void;
}) {
  if (assignments.length === 0) {
    return <div className="empty-card">Chưa có bài đã giao.</div>;
  }

  return (
    <div className="library-list">
      {assignments.map((assignment) => (
        <button className="library-item assignment-item" key={assignment.id} onClick={() => onOpenAssignment(assignment.code)}>
          <span className="file-badge">M</span>
          <div>
            <strong>{assignment.title}</strong>
            <span>{assignment.code} · {assignment.class_name} · {assignment.submitted_count}/{assignment.student_count} đã nộp</span>
          </div>
          <b>{actionLabel}</b>
        </button>
      ))}
    </div>
  );
}

function DraftShelf({
  drafts,
  onOpenDraft,
}: {
  drafts: DraftSummary[];
  onOpenDraft: (draftId: string) => void;
}) {
  if (drafts.length === 0) {
    return <div className="empty-card wide">Chưa có bản nháp. Hãy tải một file Word để bắt đầu.</div>;
  }

  return (
    <div className="draft-grid">
      {drafts.map((draft) => (
        <button className="draft-card" key={draft.id} onClick={() => onOpenDraft(draft.id)}>
          <span className="file-badge">DOC</span>
          <strong>{draft.title}</strong>
          <span>{draft.question_count} câu · {draft.warning_count} cảnh báo</span>
          <small>{draft.source_filename}</small>
        </button>
      ))}
    </div>
  );
}

type QuestionContentProps = {
  sectionType: SectionType;
  question: Question;
  editMode: boolean;
  onChange: (mutator: (question: Question) => void) => void;
};

function QuestionContent({ sectionType, question, editMode, onChange }: QuestionContentProps) {
  function updateBlocks(target: "prompt" | "options" | "statements", label: string | null, blocks: ContentBlock[]) {
    onChange((item) => {
      const markup = blocksToMarkup(blocks);
      if (target === "prompt") {
        item.prompt_blocks = blocks;
        item.prompt_markup = markup;
      }
      if (target === "options" && label && item.options) {
        item.options[label] = blocks;
        item.options_markup = { ...(item.options_markup ?? {}), [label]: markup };
      }
      if (target === "statements" && label && item.statements) {
        item.statements[label] = blocks;
        item.statements_markup = { ...(item.statements_markup ?? {}), [label]: markup };
      }
    });
  }

  return (
    <article className="question-document">
      <div className="question-kicker">Câu {question.number}</div>
      <Blocks
        blocks={question.prompt_blocks}
        markup={question.prompt_markup}
        editMode={editMode}
        onChange={(blocks) => updateBlocks("prompt", null, blocks)}
      />

      {sectionType === "single_choice" && (
        <div className="choice-list">
          {Object.entries(question.options ?? {}).map(([label, blocks]) => (
            <div className="content-row" key={label}>
              <span className="content-label">{label}</span>
              <Blocks
                blocks={blocks}
                markup={question.options_markup?.[label]}
                editMode={editMode}
                onChange={(next) => updateBlocks("options", label, next)}
              />
            </div>
          ))}
        </div>
      )}

      {sectionType === "true_false" && (
        <div className="choice-list">
          {Object.entries(question.statements ?? {}).map(([label, blocks]) => (
            <div className="content-row" key={label}>
              <span className="content-label lowercase">{label}</span>
              <Blocks
                blocks={blocks}
                markup={question.statements_markup?.[label]}
                editMode={editMode}
                onChange={(next) => updateBlocks("statements", label, next)}
              />
            </div>
          ))}
        </div>
      )}

      {editMode && <div className="edit-note"><Pencil size={15} /> Nội dung chữ đang ở chế độ sửa</div>}
    </article>
  );
}

function MarkupPanel({ sectionType, question }: { sectionType: SectionType; question: Question }) {
  const entries: Array<[string, string]> = [["Prompt", question.prompt_markup ?? blocksToMarkup(question.prompt_blocks)]];
  if (sectionType === "single_choice") {
    Object.entries(question.options ?? {}).forEach(([label, blocks]) => {
      entries.push([`Đáp án ${label}`, question.options_markup?.[label] ?? blocksToMarkup(blocks)]);
    });
  }
  if (sectionType === "true_false") {
    Object.entries(question.statements ?? {}).forEach(([label, blocks]) => {
      entries.push([`Ý ${label}`, question.statements_markup?.[label] ?? blocksToMarkup(blocks)]);
    });
  }

  const combined = entries.map(([label, value]) => `# ${label}\n${value}`).join("\n\n");
  return (
    <section className="markup-panel">
      <div className="markup-panel-head">
        <div>
          <strong>Markup câu {question.number}</strong>
          <span>Token ảnh dùng dạng [img:$img_0001$]</span>
        </div>
        <button className="secondary-button" type="button" onClick={() => void navigator.clipboard?.writeText(combined)}>
          <CopyIcon />
          <span>Copy</span>
        </button>
      </div>
      <textarea readOnly value={combined} rows={Math.min(14, Math.max(6, combined.split("\n").length + 1))} />
    </section>
  );
}

function CopyIcon() {
  return <FileText size={15} />;
}

function Blocks({
  blocks,
  markup,
  editMode,
  onChange,
}: {
  blocks: ContentBlock[];
  markup?: string;
  editMode: boolean;
  onChange: (blocks: ContentBlock[]) => void;
}) {
  if (!editMode && markup) {
    return <div className="content-blocks">{renderMarkup(markup, blocks)}</div>;
  }

  return (
    <div className={`content-blocks ${editMode ? "is-editing" : ""}`}>
      {blocks.map((block, index) => {
        if (block.type === "image") {
          return (
            <span className="asset-wrap" key={`${block.asset_id}-${index}`} style={imageWrapStyle(block)}>
              <img src={block.render_path} alt={`Công thức ${block.asset_id}`} title={block.asset_id} style={imageStyle(block)} />
              {block.status === "placeholder" && <ImageOff size={13} aria-label="Ảnh placeholder" />}
            </span>
          );
        }
        if (editMode) {
          return (
            <textarea
              key={`text-${index}`}
              value={block.text}
              aria-label="Nội dung chữ"
              rows={Math.max(2, Math.ceil(block.text.length / 80))}
              onChange={(event) => {
                const next = structuredClone(blocks);
                const target = next[index];
                if (target.type === "text") target.text = event.target.value;
                onChange(next);
              }}
            />
          );
        }
        return <span key={`text-${index}`}>{block.text}</span>;
      })}
    </div>
  );
}

function renderMarkup(markup: string, blocks: ContentBlock[]) {
  const imageBlocks = blocks.filter((block): block is Extract<ContentBlock, { type: "image" }> => block.type === "image");
  const imageIndexes = new Map<string, number>();
  const nodes: ReactNode[] = [];
  const tokenPattern = /\[img:\$([A-Za-z0-9_-]+)\$\]/g;
  let cursor = 0;
  let nodeIndex = 0;

  for (const match of markup.matchAll(tokenPattern)) {
    if (match.index > cursor) {
      nodes.push(<span key={`text-${nodeIndex++}`}>{unescapeMarkupText(markup.slice(cursor, match.index))}</span>);
    }

    const assetId = match[1];
    const occurrence = imageIndexes.get(assetId) ?? 0;
    const matchingImages = imageBlocks.filter((block) => block.asset_id === assetId);
    const imageBlock = matchingImages[occurrence] ?? matchingImages[0];
    imageIndexes.set(assetId, occurrence + 1);

    if (imageBlock) {
      nodes.push(
        <span className="asset-wrap" key={`${assetId}-${nodeIndex++}`} style={imageWrapStyle(imageBlock)}>
          <img src={imageBlock.render_path} alt={`Công thức ${assetId}`} title={assetId} style={imageStyle(imageBlock)} />
          {imageBlock.status === "placeholder" && <ImageOff size={13} aria-label="Ảnh placeholder" />}
        </span>,
      );
    } else {
      nodes.push(<span key={`missing-${nodeIndex++}`}>{match[0]}</span>);
    }

    cursor = match.index + match[0].length;
  }

  if (cursor < markup.length) {
    nodes.push(<span key={`text-${nodeIndex++}`}>{unescapeMarkupText(markup.slice(cursor))}</span>);
  }
  return nodes;
}

function blocksToMarkup(blocks: ContentBlock[]) {
  return blocks.map((block) => {
    if (block.type === "image") return `[img:$${block.asset_id}$]`;
    return escapeMarkupText(block.text);
  }).join("");
}

function escapeMarkupText(text: string) {
  return text.replace(/\\/g, "\\\\").replace(/\[/g, "\\[");
}

function unescapeMarkupText(text: string) {
  return text.replace(/\\\[/g, "[").replace(/\\\\/g, "\\");
}

function TeacherResults({ results }: { results: AssignmentResults }) {
  const submittedCount = results.submissions.filter((submission) => submission.status === "submitted").length;
  const [expandedId, setExpandedId] = useState("");
  return (
    <section className="results-strip">
      <div className="results-heading">
        <Sigma size={18} />
        <strong>Bảng điểm {results.assignment.classroom.name}</strong>
        <span>{submittedCount}/{results.assignment.student_count} đã nộp</span>
        <a className="results-export-button" href={assignmentXlsxUrl(results.assignment.code)}>
          <Download size={15} />
          <span>Xuất Excel</span>
        </a>
        <span className="results-hint">
          <Eye size={14} /> Bấm vào học sinh để xem chi tiết
        </span>
      </div>
      <div className="results-table">
        <div className="results-row header">
          <span></span>
          <span>Học sinh</span>
          <span>Trạng thái</span>
          <span>Điểm</span>
          <span>PHẦN I</span>
          <span>PHẦN II</span>
          <span>PHẦN III</span>
        </div>
        {results.submissions.map((submission) => {
          const isExpanded = expandedId === submission.id;
          return (
            <div key={submission.id}>
              <button
                type="button"
                className={`results-row clickable ${isExpanded ? "is-expanded" : ""}`}
                onClick={() => setExpandedId(isExpanded ? "" : submission.id)}
                aria-expanded={isExpanded}
                title={`Xem chi tiết bài làm của ${submission.student?.name ?? "học sinh"}`}
              >
                <span className="expand-icon">
                  {isExpanded ? <ChevronDown size={14} /> : <ChevronRight size={14} />}
                </span>
                <span>{submission.student?.name ?? "Không rõ"}</span>
                <span className={`status-pill ${submission.status}`}>{submissionStatusLabel(submission.status)}</span>
                <strong>{formatScore(submission.total_score, submission.max_score)}</strong>
                <span>{formatSectionScore(submission.grading_detail, "single_choice")}</span>
                <span>{formatSectionScore(submission.grading_detail, "true_false")}</span>
                <span>{formatSectionScore(submission.grading_detail, "short_answer")}</span>
              </button>
              {isExpanded && (
                <SubmissionDetail submission={submission} onClose={() => setExpandedId("")} />
              )}
            </div>
          );
        })}
      </div>
    </section>
  );
}

type SubmissionEntry = AssignmentResults["submissions"][number];

function SubmissionDetail({ submission, onClose }: { submission: SubmissionEntry; onClose: () => void }) {
  const student = submission.student;
  const grade = submission.grading_detail;

  if (submission.status === "not_started") {
    return (
      <div className="submission-detail">
        <div className="detail-empty">
          <BookOpen size={28} />
          <strong>{student?.name ?? "Học sinh"} chưa bắt đầu làm bài.</strong>
          <span>Khi học sinh vào bài, trạng thái sẽ tự cập nhật.</span>
        </div>
      </div>
    );
  }

  if (submission.status === "in_progress" && !grade) {
    return (
      <div className="submission-detail">
        <div className="detail-empty">
          <Clock size={28} />
          <strong>{student?.name ?? "Học sinh"} đang làm bài.</strong>
          <span>Bài làm chưa được nộp nên chưa có kết quả chấm.</span>
        </div>
      </div>
    );
  }

  return (
    <div className="submission-detail">
      <div className="detail-header">
        <div className="detail-student-info">
          <strong>{student?.name ?? "Không rõ"}</strong>
          {student?.student_code && <span className="detail-code">{student.student_code}</span>}
          <span className={`status-pill ${submission.status}`}>{submissionStatusLabel(submission.status)}</span>
        </div>
        <button className="icon-button detail-close" type="button" title="Đóng chi tiết" onClick={onClose}>
          <X size={14} />
        </button>
      </div>

      <div className="detail-meta">
        {submission.created_at && (
          <div><span>Bắt đầu:</span> <b>{formatDateTime(submission.created_at)}</b></div>
        )}
        {submission.updated_at && (
          <div><span>Cập nhật:</span> <b>{formatDateTime(submission.updated_at)}</b></div>
        )}
        {submission.submitted_at && (
          <div><span>Nộp bài:</span> <b>{formatDateTime(submission.submitted_at)}</b></div>
        )}
      </div>

      {grade ? (
        <>
          <div className="detail-scores">
            <div className="detail-total">
              <span>Tổng điểm</span>
              <strong>{grade.total_score}/{grade.max_score}</strong>
            </div>
            <div className="detail-section-scores">
              <div><span>PHẦN I</span><b>{formatSectionScore(grade, "single_choice")}</b></div>
              <div><span>PHẦN II</span><b>{formatSectionScore(grade, "true_false")}</b></div>
              <div><span>PHẦN III</span><b>{formatSectionScore(grade, "short_answer")}</b></div>
            </div>
          </div>

          <div className="detail-questions">
            <div className="detail-q-row header">
              <span>Phần</span>
              <span>Câu</span>
              <span>HS trả lời</span>
              <span>Đáp án đúng</span>
              <span>Kết quả</span>
              <span>Điểm</span>
            </div>
            {grade.questions.map((q) => (
              <QuestionDetailRow key={`${q.section_type}-${q.number}`} detail={q} />
            ))}
          </div>
        </>
      ) : (
        <div className="detail-empty compact">
          <span>Chưa có kết quả chấm điểm cho bài làm này.</span>
        </div>
      )}
    </div>
  );
}

function QuestionDetailRow({ detail }: { detail: GradingQuestionDetail }) {
  const sectionLabel = SECTION_LABELS[detail.section_type] ?? detail.section_type;
  const hasItems = detail.section_type === "true_false" && detail.items && Object.keys(detail.items).length > 0;

  return (
    <>
      <div className={`detail-q-row ${detail.correct ? "" : "is-wrong"}`}>
        <span className="detail-section-label">{sectionLabel}</span>
        <span>Câu {detail.number}</span>
        <span className="detail-answer">{formatAnswerDisplay(detail.actual, detail.section_type)}</span>
        <span className="detail-answer">{formatAnswerDisplay(detail.expected, detail.section_type)}</span>
        <span>{detail.correct ? <span className="correct-badge">✓ Đúng</span> : <span className="wrong-badge">✗ Sai</span>}</span>
        <span className="detail-score">{detail.score}/{detail.max_score}</span>
      </div>
      {hasItems && (
        <div className="detail-items">
          {Object.entries(detail.items!).map(([label, item]) => (
            <div key={label} className={`detail-item-row ${item.correct ? "" : "is-wrong"}`}>
              <span className="detail-item-label">{label})</span>
              <span>{formatItemValue(item.actual)}</span>
              <span>{formatItemValue(item.expected)}</span>
              <span>{item.correct ? <span className="correct-badge">✓</span> : <span className="wrong-badge">✗</span>}</span>
              <span className="detail-score">{item.score}/{item.max_score}</span>
            </div>
          ))}
        </div>
      )}
    </>
  );
}

function TeacherAnalytics({ analytics }: { analytics: AssignmentAnalytics }) {
  const maxBucket = Math.max(...analytics.distribution.map((bucket) => bucket.count), 1);
  return (
    <section className="analytics-strip">
      <div className="analytics-heading">
        <BarChart3 size={18} />
        <strong>Thống kê lớp</strong>
        <span>{analytics.insight}</span>
      </div>
      <div className="metric-grid">
        <div>
          <span>Đã nộp</span>
          <strong>{analytics.summary.submitted_count}/{analytics.summary.student_count}</strong>
        </div>
        <div>
          <span>Trung bình</span>
          <strong>{analytics.summary.average_score}/{analytics.summary.max_score}</strong>
        </div>
        <div>
          <span>Cao nhất</span>
          <strong>{analytics.summary.highest_score}</strong>
        </div>
        <div>
          <span>Thấp nhất</span>
          <strong>{analytics.summary.lowest_score}</strong>
        </div>
      </div>
      <div className="analytics-layout">
        <div className="distribution">
          <strong>Phổ điểm</strong>
          {analytics.distribution.map((bucket) => (
            <div className="bar-row" key={bucket.label}>
              <span>{bucket.label}</span>
              <div><i style={{ width: `${Math.max(6, (bucket.count / maxBucket) * 100)}%` }} /></div>
              <b>{bucket.count}</b>
            </div>
          ))}
        </div>
        <div className="top-wrong">
          <strong>Câu sai nhiều</strong>
          {analytics.top_wrong_questions.length === 0 && <span>Chưa có dữ liệu.</span>}
          {analytics.top_wrong_questions.map((item) => (
            <div key={`${item.section_type}-${item.number}`}>
              <span>{SECTION_LABELS[item.section_type]} câu {item.number}</span>
              <b>{item.wrong_count} sai · {Math.round(item.correct_rate * 100)}% đúng</b>
            </div>
          ))}
        </div>
      </div>
    </section>
  );
}

type StudentQuestionItem = {
  sectionType: SectionType;
  sectionTitle: string;
  sectionName: string;
  question: Question;
  key: string;
};

function StudentRunner({ code, onBack }: { code: string; onBack: () => void }) {
  const [loadedAssignment, setLoadedAssignment] = useState<Assignment | null>(null);
  const [selectedStudentId, setSelectedStudentId] = useState("");
  const [answers, setAnswers] = useState<Record<string, unknown>>({});
  const [busy, setBusy] = useState(true);
  const [saving, setSaving] = useState(false);
  const [submitted, setSubmitted] = useState(false);
  const [grade, setGrade] = useState<GradingResult | null>(null);
  const [error, setError] = useState("");
  const [startedAt, setStartedAt] = useState<string | null>(null);
  const [remainingSeconds, setRemainingSeconds] = useState<number | null>(null);
  const [timeExpired, setTimeExpired] = useState(false);
  const [studentQuestionIndex, setStudentQuestionIndex] = useState(0);

  useEffect(() => {
    let ignore = false;
    setBusy(true);
    getAssignment(code)
      .then((assignment) => {
        if (ignore) return;
        setLoadedAssignment(assignment);
        setSelectedStudentId(assignment.students[0]?.id ?? "");
        setStudentQuestionIndex(0);
      })
      .catch((caught) => {
        if (!ignore) setError(caught instanceof Error ? caught.message : "Không tìm thấy bài được giao.");
      })
      .finally(() => {
        if (!ignore) setBusy(false);
      });
    return () => {
      ignore = true;
    };
  }, [code]);

  const selectedStudent = loadedAssignment?.students.find((student) => student.id === selectedStudentId) ?? null;
  const studentQuestions = useMemo(() => {
    return loadedAssignment?.exam.sections.flatMap((section) =>
      section.questions.map((question) => ({
        sectionType: section.type,
        sectionTitle: SECTION_LABELS[section.type],
        sectionName: SECTION_NAMES[section.type],
        question,
        key: answerKey(section.type, question.number),
      })),
    ) ?? [];
  }, [loadedAssignment]);
  const currentStudentQuestion = studentQuestions[Math.min(studentQuestionIndex, Math.max(studentQuestions.length - 1, 0))];
  const answeredCount = useMemo(
    () => studentQuestions.filter((item) => isAnswered(item.sectionType, answers[item.key])).length,
    [answers, studentQuestions],
  );

  useEffect(() => {
    if (!selectedStudentId) return;
    let ignore = false;
    setSaving(true);
    setError("");
    getAssignment(code, selectedStudentId)
      .then(async (assignment) => {
        if (ignore) return;
        let nextAssignment = assignment;
        let submission = assignment.submission;
        if (!submission) {
          const started = await autosaveSubmission(code, selectedStudentId, {});
          if (ignore) return;
          nextAssignment = await getAssignment(code, selectedStudentId);
          if (ignore) return;
          submission = nextAssignment.submission ?? {
            id: started.id,
            status: started.status,
            answers: started.answers,
            created_at: started.created_at,
            updated_at: started.updated_at,
            submitted_at: started.submitted_at,
          };
        }
        setLoadedAssignment(nextAssignment);
        setAnswers(submission?.answers ?? {});
        setStartedAt(submission?.created_at ?? null);
        setSubmitted(submission?.status === "submitted");
        setTimeExpired(false);
        setGrade(submission?.grade ?? null);
        setStudentQuestionIndex(0);
      })
      .catch((caught) => {
        if (!ignore) {
          setAnswers({});
          setStartedAt(null);
          setRemainingSeconds(null);
          setTimeExpired(false);
          setSubmitted(false);
          setError(caught instanceof Error ? caught.message : "Khong the tai bai dang lam.");
        }
      })
      .finally(() => {
        if (!ignore) setSaving(false);
      });
    return () => {
      ignore = true;
    };
  }, [code, selectedStudentId]);

  useEffect(() => {
    if (!loadedAssignment || !startedAt || submitted) {
      setRemainingSeconds(null);
      return;
    }
    const assignment = loadedAssignment;
    const start = startedAt;

    function updateRemaining() {
      const startedMs = new Date(start).getTime();
      const durationMs = assignment.duration_minutes * 60 * 1000;
      const remaining = Math.max(0, Math.ceil((startedMs + durationMs - Date.now()) / 1000));
      setRemainingSeconds(remaining);
      if (remaining === 0 && !timeExpired) {
        setTimeExpired(true);
      }
    }

    updateRemaining();
    const timerId = window.setInterval(updateRemaining, 1000);
    return () => window.clearInterval(timerId);
  }, [loadedAssignment, startedAt, submitted, timeExpired]);

  useEffect(() => {
    if (!timeExpired || submitted || !selectedStudentId) return;
    void handleSubmit(true);
  }, [timeExpired, submitted, selectedStudentId]);

  async function updateAnswer(key: string, value: unknown) {
    const next = { ...answers, [key]: value };
    setAnswers(next);
    if (!selectedStudentId || submitted || timeExpired) return;
    setSaving(true);
    try {
      await autosaveSubmission(code, selectedStudentId, next);
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : "Không thể lưu bài làm.");
    } finally {
      setSaving(false);
    }
  }

  async function handleSubmit(auto = false) {
    if (!selectedStudentId) return;
    const missingCount = studentQuestions.length - answeredCount;
    if (!auto && missingCount > 0 && !window.confirm(`Bạn còn ${missingCount} câu chưa trả lời. Vẫn nộp bài?`)) {
      return;
    }
    setSaving(true);
    setError("");
    try {
      const result = await submitAssignment(code, selectedStudentId, answers);
      setGrade(result.grade);
      setSubmitted(true);
      if (auto) setError("Đã hết thời gian. Hệ thống đã tự nộp bài.");
      // Re-fetch to get correct_answer in exam when show_answers is on
      try {
        const updated = await getAssignment(code, selectedStudentId);
        setLoadedAssignment(updated);
      } catch { /* ignore re-fetch failure */ }
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : auto ? "Hết giờ nhưng chưa thể tự nộp bài." : "Không thể nộp bài.");
    } finally {
      setSaving(false);
    }
  }

  if (busy) {
    return (
      <main className="student-shell centered">
        <LoaderCircle className="spin" size={30} />
      </main>
    );
  }

  if (!loadedAssignment) {
    return (
      <main className="student-shell centered">
        <div className="error-banner">{error || "Không tìm thấy bài được giao."}</div>
        <button className="secondary-button" onClick={onBack}>Quay lại</button>
      </main>
    );
  }

  return (
    <main className="student-shell">
      <header className="student-header">
        <div className="brand-line">
          <button
            className="brand-mark brand-home"
            type="button"
            title="Về trang tạo đề"
            aria-label="Về trang tạo đề"
            onClick={onBack}
          >
            T
          </button>
          <span>Học cùng cô Tuyết</span>
        </div>
        <div className="student-meta">
          <strong>{loadedAssignment.title}</strong>
          <span>Lớp {loadedAssignment.classroom.name} · {loadedAssignment.code} · {loadedAssignment.duration_minutes} phút</span>
        </div>
        <div className={`student-timer ${remainingSeconds !== null && remainingSeconds <= 60 ? "is-danger" : ""}`}>
          <Clock size={18} />
          <strong>{submitted ? "Đã nộp" : remainingSeconds === null ? "--:--" : formatRemainingTime(remainingSeconds)}</strong>
        </div>
        <button className="secondary-button" disabled={saving || submitted || !selectedStudentId} onClick={() => void handleSubmit()}>
          {saving ? <LoaderCircle className="spin" size={18} /> : <Send size={18} />}
          <span>{submitted ? "Đã nộp" : "Nộp bài"}</span>
        </button>
      </header>

      {error && <div className="error-banner workspace-error">{error}</div>}

      {submitted ? (
        <StudentResultScreen
          grade={grade}
          showScore={loadedAssignment.show_score}
          showAnswers={loadedAssignment.show_answers}
          studentName={selectedStudent?.name ?? ""}
          answeredCount={answeredCount}
          totalQuestions={studentQuestions.length}
          questions={studentQuestions}
        />
      ) : (
        <>
          <section className="student-picker">
            <label htmlFor="student-select">Học sinh</label>
            <select
              id="student-select"
              value={selectedStudentId}
              disabled={saving}
              onChange={(event) => {
                setSelectedStudentId(event.target.value);
                setAnswers({});
                setStartedAt(null);
                setRemainingSeconds(null);
                setTimeExpired(false);
                setStudentQuestionIndex(0);
                setSubmitted(false);
                setGrade(null);
                setError("");
              }}
            >
              {loadedAssignment.students.map((student) => (
                <option key={student.id} value={student.id}>
                  {student.student_code} - {student.name}
                </option>
              ))}
            </select>
            <span>{saving ? "Đang lưu" : "Sẵn sàng"}</span>
          </section>

          <section className="student-progress">
            <div className="progress-head">
              <strong>{answeredCount}/{studentQuestions.length} câu đã làm</strong>
              <span>Câu {studentQuestionIndex + 1}/{studentQuestions.length}</span>
            </div>
            <div className="progress-track">
              <i style={{ width: `${studentQuestions.length ? (answeredCount / studentQuestions.length) * 100 : 0}%` }} />
            </div>
            <div className="student-question-nav" aria-label="Danh sách câu hỏi">
              {studentQuestions.map((item, index) => (
                <button
                  key={`${item.sectionType}-${item.question.number}`}
                  className={[
                    index === studentQuestionIndex ? "is-active" : "",
                    isAnswered(item.sectionType, answers[item.key]) ? "is-answered" : "",
                  ].filter(Boolean).join(" ")}
                  onClick={() => setStudentQuestionIndex(index)}
                  aria-label={`${item.sectionTitle} câu ${item.question.number}`}
                >
                  {index + 1}
                </button>
              ))}
            </div>
          </section>

          <div className="student-paper single-question">
            {currentStudentQuestion && (
              <section className="student-section" key={`${currentStudentQuestion.sectionType}-${currentStudentQuestion.question.number}`}>
                <div className="student-section-title">
                  <strong>{currentStudentQuestion.sectionTitle}</strong>
                  <span>{currentStudentQuestion.sectionName}</span>
                </div>
                <article className="student-question">
                  <QuestionContent
                    sectionType={currentStudentQuestion.sectionType}
                    question={currentStudentQuestion.question}
                    editMode={false}
                    onChange={() => undefined}
                  />
                  <StudentAnswerControl
                    sectionType={currentStudentQuestion.sectionType}
                    question={currentStudentQuestion.question}
                    value={answers[currentStudentQuestion.key]}
                    disabled={timeExpired}
                    onChange={(value) => void updateAnswer(currentStudentQuestion.key, value)}
                  />
                </article>
                <div className="student-stepper">
                  <button
                    className="secondary-button"
                    disabled={studentQuestionIndex === 0}
                    onClick={() => setStudentQuestionIndex((index) => Math.max(0, index - 1))}
                  >
                    Câu trước
                  </button>
                  <button
                    className="primary-button"
                    disabled={studentQuestionIndex >= studentQuestions.length - 1}
                    onClick={() => setStudentQuestionIndex((index) => Math.min(studentQuestions.length - 1, index + 1))}
                  >
                    Câu sau
                  </button>
                </div>
              </section>
            )}
          </div>
        </>
      )}
    </main>
  );
}

function StudentResultScreen({
  grade,
  showScore,
  showAnswers,
  studentName,
  answeredCount,
  totalQuestions,
  questions,
}: {
  grade: GradingResult | null;
  showScore: boolean;
  showAnswers: boolean;
  studentName: string;
  answeredCount: number;
  totalQuestions: number;
  questions: StudentQuestionItem[];
}) {
  if (!showScore || !grade) {
    return (
      <section className="student-result-panel waiting">
        <div className="result-hero-icon">
          <Check size={34} />
        </div>
        <p className="eyebrow">Đã nộp bài</p>
        <h1>{studentName ? `${studentName} đã nộp bài` : "Bài làm đã được gửi"}</h1>
        <p>Chờ giáo viên công bố điểm. Bài làm của em đã được hệ thống ghi nhận.</p>
        <div className="result-mini-stats">
          <span>{answeredCount}/{totalQuestions} câu đã trả lời</span>
        </div>
      </section>
    );
  }

  const correctCount = grade.questions.filter((item) => item.correct).length;
  const scorePercent = grade.max_score > 0 ? Math.round((grade.total_score / grade.max_score) * 100) : 0;

  return (
    <section className="student-result-panel">
      <div className="result-summary-card">
        <div className="result-score-ring" style={{ "--score-percent": `${scorePercent}%` } as CSSProperties}>
          <strong>{grade.total_score}</strong>
          <span>/{grade.max_score}</span>
        </div>
        <div>
          <p className="eyebrow">Kết quả bài làm</p>
          <h1>{studentName ? `Làm tốt rồi, ${studentName}` : "Bài làm đã được chấm"}</h1>
          <p>{correctCount}/{grade.questions.length} câu đúng. {showAnswers ? "Em có thể xem lại đáp án bên dưới." : "Giáo viên chưa công bố đáp án chi tiết."}</p>
        </div>
      </div>

      <div className="result-section-grid">
        <div><span>PHẦN I</span><strong>{formatSectionScore(grade, "single_choice")}</strong></div>
        <div><span>PHẦN II</span><strong>{formatSectionScore(grade, "true_false")}</strong></div>
        <div><span>PHẦN III</span><strong>{formatSectionScore(grade, "short_answer")}</strong></div>
      </div>

      <div className="student-result-list">
        <strong>Danh sách câu</strong>
        {grade.questions.map((detail) => {
          const item = questions.find(
            (questionItem) => questionItem.sectionType === detail.section_type && questionItem.question.number === detail.number,
          );
          return (
            <StudentResultQuestion
              key={`${detail.section_type}-${detail.number}`}
              detail={detail}
              showAnswers={showAnswers}
              questionItem={item}
            />
          );
        })}
      </div>
    </section>
  );
}

function StudentResultQuestion({
  detail,
  showAnswers,
  questionItem,
}: {
  detail: GradingQuestionDetail;
  showAnswers: boolean;
  questionItem?: StudentQuestionItem;
}) {
  const reviewQuestion = questionItem && showAnswers
    ? { ...questionItem.question, correct_answer: detail.expected as Question["correct_answer"] }
    : null;

  return (
    <div className={`student-result-question ${detail.correct ? "is-correct" : "is-wrong"}`}>
      <div>
        <span>{SECTION_LABELS[detail.section_type]} · Câu {detail.number}</span>
        <strong>{detail.correct ? "Đúng" : "Sai"} · {detail.score}/{detail.max_score} điểm</strong>
      </div>
      <div className="student-result-answer">
        <span>Em chọn: {formatAnswerDisplay(detail.actual, detail.section_type)}</span>
        {showAnswers && <span>Đáp án: {formatAnswerDisplay(detail.expected, detail.section_type)}</span>}
      </div>
      {reviewQuestion && (
        <div className="student-result-review">
          <QuestionContent
            sectionType={detail.section_type}
            question={reviewQuestion}
            editMode={false}
            onChange={() => undefined}
          />
          <StudentAnswerControl
            sectionType={detail.section_type}
            question={reviewQuestion}
            value={detail.actual}
            disabled={true}
            onChange={() => undefined}
            showCorrect={true}
          />
        </div>
      )}
    </div>
  );
}

function StudentSubmittedNotice({ showScore }: { showScore: boolean }) {
  return (
    <section className="student-grade submitted-note">
      <div>
        <Check size={20} />
        <strong>Đã nộp bài</strong>
      </div>
      <span>{showScore ? "Điểm sẽ hiện khi hệ thống chấm xong." : "Chờ giáo viên công bố kết quả."}</span>
    </section>
  );
}

function StudentGrade({ grade, showAnswers }: { grade: GradingResult; showAnswers: boolean }) {
  return (
    <section className="student-grade">
      <div>
        <Sigma size={20} />
        <strong>{grade.total_score}/{grade.max_score}</strong>
      </div>
      <span>PHẦN I {formatSectionScore(grade, "single_choice")}</span>
      <span>PHẦN II {formatSectionScore(grade, "true_false")}</span>
      <span>PHẦN III {formatSectionScore(grade, "short_answer")}</span>
      {showAnswers && <span>Đáp án đã được công bố</span>}
    </section>
  );
}

function StudentAnswerControl({
  sectionType,
  question,
  value,
  disabled,
  onChange,
  showCorrect = false,
}: {
  sectionType: SectionType;
  question: Question;
  value: unknown;
  disabled: boolean;
  onChange: (value: unknown) => void;
  showCorrect?: boolean;
}) {
  const correctAnswer = showCorrect ? question.correct_answer : undefined;

  if (sectionType === "single_choice") {
    return (
      <div className="student-answer">
        <div className={`segment-control ${showCorrect ? "show-correct" : ""}`}>
          {Object.keys(question.options ?? { A: [], B: [], C: [], D: [] }).map((answer) => {
            const isSelected = value === answer;
            const isCorrect = showCorrect && typeof correctAnswer === "string" && correctAnswer.toUpperCase() === answer.toUpperCase();
            const isWrong = showCorrect && isSelected && !isCorrect;
            return (
              <button
                key={answer}
                disabled={disabled}
                className={[
                  isSelected && !showCorrect ? "is-active" : "",
                  isCorrect ? "is-correct" : "",
                  isWrong ? "is-wrong" : "",
                ].filter(Boolean).join(" ")}
                onClick={() => onChange(answer)}
              >
                {answer}
                {isCorrect && <Check size={13} />}
              </button>
            );
          })}
        </div>
        {showCorrect && typeof correctAnswer === "string" && (
          <div className="correct-answer-note">
            <Check size={14} /> Đáp án đúng: <b>{correctAnswer}</b>
          </div>
        )}
      </div>
    );
  }

  if (sectionType === "true_false") {
    const answers = (value ?? {}) as Record<string, string>;
    const correctAnswers = showCorrect && typeof correctAnswer === "object" && correctAnswer ? correctAnswer as Record<string, string> : null;
    return (
      <div className="student-answer truth-list">
        {Object.keys(question.statements ?? { a: [], b: [], c: [], d: [] }).map((label) => {
          const correctValue = correctAnswers?.[label];
          return (
            <div key={label}>
              <span>{label}</span>
              <div className={`segment-control compact ${showCorrect ? "show-correct" : ""}`}>
                {["Đ", "S"].map((answer) => {
                  const isSelected = answers[label] === answer;
                  const isCorrect = showCorrect && correctValue === answer;
                  const isWrong = showCorrect && isSelected && !isCorrect;
                  return (
                    <button
                      key={answer}
                      disabled={disabled}
                      className={[
                        isSelected && !showCorrect ? "is-active" : "",
                        isCorrect ? "is-correct" : "",
                        isWrong ? "is-wrong" : "",
                      ].filter(Boolean).join(" ")}
                      onClick={() => onChange({ ...answers, [label]: answer })}
                    >
                      {answer}
                    </button>
                  );
                })}
              </div>
              {showCorrect && correctValue && (
                <span className={answers[label] === correctValue ? "item-correct-mark" : "item-wrong-mark"}>
                  {answers[label] === correctValue ? "✓" : "✗"}
                </span>
              )}
            </div>
          );
        })}
      </div>
    );
  }

  return (
    <div className="student-answer">
      <input
        className="text-input"
        disabled={disabled}
        value={typeof value === "string" ? value : ""}
        onChange={(event) => onChange(event.target.value)}
      />
      {showCorrect && typeof correctAnswer === "string" && (
        <div className="correct-answer-note">
          <Check size={14} /> Đáp án đúng: <b>{correctAnswer}</b>
        </div>
      )}
    </div>
  );
}

function AnswerEditor({ sectionType, question, onChange }: { sectionType: SectionType; question: Question; onChange: (mutator: (question: Question) => void) => void }) {
  return (
    <div className="inspector-inner">
      <div className="aside-heading">
        <strong>Câu {question.number}</strong>
        <span>Đáp án và điểm</span>
      </div>

      {sectionType === "single_choice" && (
        <div className="field-group">
          <label>Đáp án đúng</label>
          <div className="segment-control">
            {["A", "B", "C", "D"].map((answer) => (
              <button
                key={answer}
                className={question.correct_answer === answer ? "is-active" : ""}
                onClick={() => onChange((item) => void (item.correct_answer = answer))}
              >
                {answer}
              </button>
            ))}
          </div>
        </div>
      )}

      {sectionType === "true_false" && (
        <div className="field-group">
          <label>Đáp án từng ý</label>
          <div className="truth-list">
            {["a", "b", "c", "d"].map((label) => {
              const answers = (question.correct_answer ?? {}) as Record<string, string>;
              return (
                <div key={label}>
                  <span>{label}</span>
                  <div className="segment-control compact">
                    {["Đ", "S"].map((answer) => (
                      <button
                        key={answer}
                        className={answers[label] === answer ? "is-active" : ""}
                        onClick={() => onChange((item) => {
                          const next = { ...((item.correct_answer ?? {}) as Record<string, string>) };
                          next[label] = answer;
                          item.correct_answer = next;
                        })}
                      >
                        {answer}
                      </button>
                    ))}
                  </div>
                </div>
              );
            })}
          </div>
        </div>
      )}

      {sectionType === "short_answer" && (
        <div className="field-group">
          <label htmlFor="short-answer">Đáp án</label>
          <input
            id="short-answer"
            className="text-input"
            value={typeof question.correct_answer === "string" ? question.correct_answer : ""}
            onChange={(event) => onChange((item) => void (item.correct_answer = event.target.value))}
          />
        </div>
      )}

      <div className="field-group">
        <label htmlFor="question-score">Điểm câu</label>
        <div className="number-field">
          <input
            id="question-score"
            type="number"
            min="0"
            step="0.25"
            value={question.score}
            onChange={(event: ChangeEvent<HTMLInputElement>) => {
              const value = Number(event.target.value);
              onChange((item) => void (item.score = Number.isFinite(value) ? value : 0));
            }}
          />
          <span>điểm</span>
        </div>
      </div>
    </div>
  );
}

function studentCodeFromHash() {
  const match = window.location.hash.match(/^#student\/(.+)$/);
  return match ? decodeURIComponent(match[1]) : "";
}

function answerKey(sectionType: SectionType, questionNumber: number) {
  return `${sectionType}:${questionNumber}`;
}

function isAnswered(sectionType: SectionType, value: unknown) {
  if (sectionType === "true_false") {
    const answers = (value ?? {}) as Record<string, unknown>;
    return ["a", "b", "c", "d"].every((label) => answers[label] === "Đ" || answers[label] === "S");
  }
  if (sectionType === "short_answer") {
    return typeof value === "string" && value.trim().length > 0;
  }
  return typeof value === "string" && value.length > 0;
}

function formatScore(score: number | null, maxScore: number | null) {
  if (score == null || maxScore == null) return "-";
  return `${score}/${maxScore}`;
}

function formatDateTime(isoString: string): string {
  try {
    const date = new Date(isoString);
    if (isNaN(date.getTime())) return isoString;
    return date.toLocaleString("vi-VN", {
      day: "2-digit",
      month: "2-digit",
      year: "numeric",
      hour: "2-digit",
      minute: "2-digit",
      second: "2-digit",
    });
  } catch {
    return isoString;
  }
}

function formatAnswerDisplay(value: unknown, sectionType: SectionType): string {
  if (value == null || value === "") return "—";
  if (sectionType === "true_false" && typeof value === "object") {
    const entries = Object.entries(value as Record<string, string>);
    if (entries.length === 0) return "—";
    return entries.map(([label, val]) => `${label}:${val}`).join(" ");
  }
  return String(value);
}

function formatItemValue(value: unknown): string {
  if (value == null || value === "") return "—";
  return String(value);
}

function submissionStatusLabel(status: "not_started" | "in_progress" | "submitted") {
  if (status === "submitted") return "Đã nộp";
  if (status === "in_progress") return "Đang làm";
  return "Chưa làm";
}

function formatSectionScore(grade: GradingResult | null, sectionType: SectionType) {
  const section = grade?.by_section?.[sectionType];
  if (!section) return "-";
  return `${section.score}/${section.max_score}`;
}

function formatRemainingTime(totalSeconds: number) {
  const seconds = Math.max(0, totalSeconds);
  const hours = Math.floor(seconds / 3600);
  const minutes = Math.floor((seconds % 3600) / 60);
  const rest = seconds % 60;
  if (hours > 0) {
    return `${hours}:${String(minutes).padStart(2, "0")}:${String(rest).padStart(2, "0")}`;
  }
  return `${minutes}:${String(rest).padStart(2, "0")}`;
}

function imageStyle(block: Extract<ContentBlock, { type: "image" }>): CSSProperties | undefined {
  if (!block.display_width_px || !block.display_height_px) return undefined;
  return {
    width: `${block.display_width_px}px`,
    height: `${block.display_height_px}px`,
  };
}

function imageWrapStyle(block: Extract<ContentBlock, { type: "image" }>): CSSProperties | undefined {
  if (!block.display_height_px) return undefined;
  const shift = Math.min(0.62, Math.max(0.18, block.display_height_px / 72));
  return { "--formula-align": `-${shift.toFixed(2)}em` } as CSSProperties;
}

export default App;
