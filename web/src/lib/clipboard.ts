// Copy a text to the clipboard, from the page alone (ADR 0031): the web view's asynchronous
// clipboard where it allows it, else the page's own copy command.

/** Whether the text was copied. */
export async function copyText(text: string, target: Window = window): Promise<boolean> {
  try {
    await target.navigator.clipboard.writeText(text);
    return true;
  } catch {
    return copyByCommand(text, target.document);
  }
}

function copyByCommand(text: string, document: Document): boolean {
  const field = document.createElement("textarea");
  field.value = text;
  field.setAttribute("readonly", "");
  field.style.position = "fixed";
  field.style.opacity = "0";
  document.body.append(field);
  field.select();
  try {
    // Deprecated, but still the only copy a page has where the asynchronous clipboard is refused
    // eslint-disable-next-line @typescript-eslint/no-deprecated
    return document.execCommand("copy");
  } catch {
    return false;
  } finally {
    field.remove();
  }
}
