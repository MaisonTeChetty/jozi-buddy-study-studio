export interface AuthStatus { authenticated: boolean; csrf: string; setup_required?: boolean|null; mfa_required?: boolean; mfa_enabled?: boolean|null; profile?: {name: string | null}|null }
export interface PageText { page: number; text: string; scanned: boolean }
export interface Document { id: string; title: string; filename: string; created: number; status: 'indexing'|'ready'|'needs_aws'; indexed: number; page_count: number; chunk_count: number; scanned_pages: number[]; redactions: Record<string,number>; error?: string|null; pages?: PageText[] }
export interface Citation { document_id: string; page: number; excerpt: string }
export interface Answer { answer: string; supported: boolean; citations: Citation[] }
export interface PracticeQuestion { id: string; type: 'mcq'|'short'|'medium'; prompt: string; options: string[]; marks: number; pages: number[]; needs_review: boolean }
export interface Question extends PracticeQuestion { correct_index: number|null; model_answer: string; rubric: string; explanation: string }
export interface Quiz { id: string; document_id: string; title: string; created: number; questions: Question[] }
export interface QuizSummary { id: string; document_id: string; title: string; count: number; created: number; needs_review: boolean }
export interface Grade { score: number; feedback: string; pages: number[]; correct_answer: string }
export interface Attempt { id: string; quiz_id: string; document_id: string; title: string; mode: 'practice'|'self-test'; questions: PracticeQuestion[]; answers: Record<string,string>; grades: Record<string,Grade>; submitted: boolean; created: number; score: number; total_marks: number }
export interface Limits {text: number; quiz: number; voice_seconds: number}
export interface Security {mfa_enabled: boolean; limits: Limits; usage: Limits; tokens: {input:number;output:number}; controls: Record<string,boolean|string>; data_location: string; events: {id:string;event:string;decision:string;reason:string;timestamp:number}[]}
