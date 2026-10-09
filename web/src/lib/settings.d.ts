/* Generated from edrockmaster/desktop/schemas/settings.schema.json by 'pnpm types': do not edit. */

/**
 * The desktop application's settings (ADR 0020): what settings() returns and save_settings() takes. Names in the player's language.
 */
export interface Settings {
  alerts: {
    thresholds: {
      commodity: string;
      name: string;
      /**
       * Minimum proportion, in percent, that raises an alert; null for none.
       */
      threshold: number | null;
    }[];
    minimumContent: "low" | "medium" | "high";
    /**
     * Minimum remaining reserve, in percent; null for none.
     */
    minimumRemaining: number | null;
    cores: boolean;
  };
  sound: boolean;
  recordJournal: boolean;
  /**
   * @minItems 1
   */
  activities: ["mining" | "combat" | "trade" | "engineering", ...("mining" | "combat" | "trade" | "engineering")[]];
  language: "auto" | "en" | "fr";
  /**
   * Set by hand; null: where the game usually writes it. Used from the next start.
   */
  journalFolder: string | null;
  /**
   * The folder read now (read only).
   */
  journalFolderInUse: string | null;
}
