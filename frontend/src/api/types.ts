export interface User {
  id: string;
  email: string;
  full_name: string;
  phone?: string | null;
  role: "citizen" | "authority" | "admin";
  department_name?: string | null;
  ward?: string | null;
}

export interface ReportOut {
  code: string;
  title: string;
  description?: string;
  status: string;
  category_name?: string | null;
  subcategory?: string | null;
  ai_severity?: number | null;
  ai_urgency?: number | null;
  ai_keywords?: string[] | null;
  latitude: number;
  longitude: number;
  landmark?: string | null;
  ward?: string | null;
  cluster_code?: string | null;
  created_at: string;
  media_count?: number;
}

export interface MediaItem {
  id: string;
  kind: "image" | "video" | "audio";
  url: string;
  created_at?: string;
}

export interface ProblemCluster {
  code: string;
  title: string;
  status: string;
  score?: number;
  priority_score?: number;
  level?: string;
  priority_level?: string;
  category?: string | null;
  report_count: number;
  affected_population_est?: number;
  top_factors?: string[];
  last_reported_at?: string;
}

export type MapPoint = {
  id: string;
  type: "problem" | "report" | "facility" | "gap";
  lat: number;
  lng: number;
  title: string;
  status?: string;
  priority_level?: string;
  category?: string | null;
  category_color?: string;
  report_count?: number;
  facility_type?: string;
  gap_score?: number;
  severity_label?: string;
  nearest_distance_km?: number | null;
  insight_text?: string;
};

export interface ActionItem {
  code: string;
  cluster_id: string;
  department_id: string;
  department?: { name: string };
  officer_id?: string | null;
  team_name?: string | null;
  resources_needed?: string | null;
  estimated_cost?: number | null;
  deadline?: string | null;
  status: string;
  notes?: string | null;
  created_at: string;
  cluster?: { code: string; title: string; priority_level?: string };
}
