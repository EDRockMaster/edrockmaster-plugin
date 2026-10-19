/* Generated from edrockmaster/desktop/schemas/phone.schema.json by 'pnpm types': do not edit. */

/**
 * The Phone and tablet section of Settings (ADR 0055, ADR 0056): what phone(), set_phone(), new_phone_link() and use_phone_address() return.
 */
export interface Phone {
  /**
   * The player turned the local server on.
   */
  enabled: boolean;
  port: number;
  /**
   * The local server listens now.
   */
  listening: boolean;
  /**
   * Why it does not listen although turned on.
   */
  error: "portInUse" | null;
  /**
   * The address of the QR code, with the link key; null when nothing listens, or without a network address.
   */
  link: string | null;
  /**
   * The QR code of the link, as inline SVG.
   */
  qr: string | null;
  /**
   * The same link through the computer's other local addresses, the player may choose for the QR code.
   */
  otherLinks: {
    address: string;
    link: string;
  }[];
}
