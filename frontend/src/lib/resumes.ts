import { supabase } from "./supabase";
import { api } from "./api";

export type Resume = {
  id: string;
  title: string;
  file_name: string | null;
  file_path: string | null;
  content: string;
  updated_at: string;
};

const COLUMNS = "id,title,file_name,file_path,content,updated_at";

export async function listResumes(): Promise<Resume[]> {
  const { data, error } = await supabase
    .from("resumes")
    .select(COLUMNS)
    .order("updated_at", { ascending: false });
  if (error) throw error;
  return data;
}

export async function uploadResume(userId: string, file: File): Promise<Resume> {
  // 1. Extract the text on the backend (fails early on bad files)
  const { text } = await api.extractResumeText(file);

  // 2. Create the row; Postgres fills id and user_id
  const { data: row, error } = await supabase
    .from("resumes")
    .insert({ title: file.name.replace(/\.(pdf|docx)$/i, ""), file_name: file.name, content: text })
    .select(COLUMNS)
    .single();
  if (error) throw error;

  // 3. Store the original under <userId>/<resumeId>.<ext>
  const ext = file.name.split(".").pop()?.toLowerCase() ?? "pdf";
  const path = `${userId}/${row.id}.${ext}`;
  const upload = await supabase.storage.from("resumes").upload(path, file, { contentType: file.type });
  if (upload.error) {
    await supabase.from("resumes").delete().eq("id", row.id); // don't leave a half-saved resume
    throw upload.error;
  }

  const { data: saved, error: e2 } = await supabase
    .from("resumes").update({ file_path: path }).eq("id", row.id).select(COLUMNS).single();
  if (e2) throw e2;
  return saved;
}

export async function saveResume(id: string, changes: { title: string; content: string }): Promise<Resume> {
  const { data, error } = await supabase
    .from("resumes").update(changes).eq("id", id).select(COLUMNS).single();
  if (error) throw error;
  return data;
}

export async function deleteResume(resume: Resume): Promise<void> {
  if (resume.file_path) await supabase.storage.from("resumes").remove([resume.file_path]);
  const { error } = await supabase.from("resumes").delete().eq("id", resume.id);
  if (error) throw error;
}

// Private bucket → a link that works for 60 seconds
export async function fileUrl(path: string): Promise<string> {
  const { data, error } = await supabase.storage.from("resumes").createSignedUrl(path, 60);
  if (error) throw error;
  return data.signedUrl;
}