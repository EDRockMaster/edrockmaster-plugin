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
    /**
     * Limpets on board at which to alert (ADR 0042); null for no alert.
     */
    limpets: number | null;
  };
  sound: boolean;
  recordJournal: boolean;
  /**
   * @minItems 1
   */
  activities: [
    "mining" | "combat" | "trade" | "engineering" | "communityGoals",
    ...("mining" | "combat" | "trade" | "engineering" | "communityGoals")[]
  ];
  language: "auto" | "en" | "fr";
  /**
   * Set by hand; null: where the game usually writes it. Used from the next start.
   */
  journalFolder: string | null;
  /**
   * The folder read now (read only).
   */
  journalFolderInUse: string | null;
  /**
   * Where the journal recordings go (read only); the interface can open it.
   */
  recordingsFolder: string;
  /**
   * Where the application's log file is (read only); the interface can open it.
   */
  logsFolder: string;
  /**
   * The community sources the application may ask, on the player's action only (ADR 0039).
   */
  sources: {
    /**
     * Spansh: rings and their hotspots.
     */
    spansh: boolean;
    /**
     * Ardent Insight: the markets that buy a commodity.
     */
    ardent: boolean;
  };
  /**
   * Updates of the installed application (ADR 0053).
   */
  updates: {
    /**
     * Installed to update itself; false for a clone or a CI build (read only).
     */
    installed: boolean;
    /**
     * Check for a newer version, and download it.
     */
    check: boolean;
    /**
     * stable: productions only; beta: candidates too. The build's channel unless another is chosen.
     */
    channel: "stable" | "beta";
  };
}
