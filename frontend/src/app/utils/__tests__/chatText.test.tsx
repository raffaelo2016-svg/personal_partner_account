// @vitest-environment node
import { renderToStaticMarkup } from 'react-dom/server';
import { describe, expect, it } from 'vitest';
import { decodeChatText } from '../chatText';

describe('chat text', () => {
  it('restores quotes in saved messages', () => {
    expect(decodeChatText('Указали &quot;Льготный период&quot;.')).toBe('Указали "Льготный период".');
    expect(decodeChatText('&#x27;текст&#39; &amp; &lt;слово&gt;')).toBe("'текст' & <слово>");
  });

  it('preserves ordinary text and decodes only once', () => {
    expect(decodeChatText('«Период» "текст"')).toBe('«Период» "текст"');
    expect(decodeChatText('&amp;quot;')).toBe('&quot;');
  });

  it('renders decoded markup as text without creating HTML elements', () => {
    const markup = renderToStaticMarkup(<p>{decodeChatText('&lt;img src=x onerror=alert(1)&gt;')}</p>);
    expect(markup).toBe('<p>&lt;img src=x onerror=alert(1)&gt;</p>');
  });
});
