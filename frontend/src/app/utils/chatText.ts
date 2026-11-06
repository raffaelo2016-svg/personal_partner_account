const entities: Record<string, string> = {
  '&quot;': '"',
  '&#x27;': "'",
  '&#39;': "'",
  '&lt;': '<',
  '&gt;': '>',
  '&amp;': '&',
};

// Older Bitrix messages were HTML-escaped before storage. Decode one layer
// and render the result as React text, never as HTML.
export function decodeChatText(text: string): string {
  return text.replace(/&(?:quot|#x27|#39|lt|gt|amp);/g, (entity) => entities[entity]);
}
