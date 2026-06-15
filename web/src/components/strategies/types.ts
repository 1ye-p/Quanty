/** Shared types for strategy version management. */

export interface Version {
  version_id: string
  config_text: string
  config_format?: string
  summary: string
  created_at: string
}
