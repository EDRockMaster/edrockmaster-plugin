/* Generated from edrockmaster/desktop/schemas/live_view.schema.json by 'pnpm types': do not edit. */

export type Activity = "mining" | "combat" | "trade" | "engineering";

/**
 * What the core shows of the activities, pushed to the interface after each change (ADR 0020, ADR 0021). Texts of the blocks are already in the player's language.
 */
export interface LiveView {
  version: 1;
  /**
   * The language of the texts, and of the interface's own catalogue.
   */
  language: "en" | "fr";
  /**
   * The last activity that progressed.
   */
  current: "mining" | "combat" | "trade" | "engineering";
  /**
   * The activities the player shows, in display order.
   */
  activities: Block[];
  /**
   * Local data reset or unavailable (ADR 0018), until dismissed.
   */
  notice: "reset" | "unavailable" | null;
  journal: {
    /**
     * The journal folder; null when none was found.
     */
    folder: string | null;
    /**
     * The journal file being read.
     */
    file: string | null;
  };
}
export interface Block {
  activity: Activity;
  status: string;
  lines: {
    label: string;
    value: string;
  }[];
  alert: string | null;
  canReset: boolean;
}
