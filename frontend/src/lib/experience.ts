import { supabase } from "./supabase";

/** Experience bank: things you've done that may not be on your resume.
 *  The tailoring agent can search these and copy them in (see backend/app/tailor/bank.py). */
export type ExperienceKind = "job" | "project" | "education" | "volunteer" | "skill" | "other";

export type ExperienceItem = {
  id: string;
  kind: ExperienceKind;
  title: string;
  organization: string;
  dates: string;
  bullets: string[];
  skills: string[];
};

export type ExperienceDraft = Omit<ExperienceItem, "id">;

const COLUMNS = "id,kind,title,organization,dates,bullets,skills";

export async function listExperience(): Promise<ExperienceItem[]> {
  const { data, error } = await supabase
    .from("experience_items")
    .select(COLUMNS)
    .order("created_at", { ascending: false });
  if (error) throw error;
  return data;
}

export async function createExperience(item: ExperienceDraft): Promise<ExperienceItem> {
  // user_id defaults to auth.uid() in Postgres
  const { data, error } = await supabase.from("experience_items").insert(item).select(COLUMNS).single();
  if (error) throw error;
  return data;
}

export async function updateExperience(id: string, item: ExperienceDraft): Promise<ExperienceItem> {
  const { data, error } = await supabase
    .from("experience_items").update(item).eq("id", id).select(COLUMNS).single();
  if (error) throw error;
  return data;
}

export async function deleteExperience(id: string): Promise<void> {
  const { error } = await supabase.from("experience_items").delete().eq("id", id);
  if (error) throw error;
}
