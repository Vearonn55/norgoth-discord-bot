/**
 * Conversion between TinyMCE HTML and the Discord-flavored markdown subset
 * that the bot actually delivers. Discord renders markdown, not HTML, so the
 * editor output has to be flattened before it is stored on a campaign or an
 * automation message template.
 */

export const DISCORD_MARKDOWN_SPEC_VERSION = 1;

export function isSafeHttpUrl(href: string): boolean {
  try {
    const parsed = new URL(href);
    return parsed.protocol === "http:" || parsed.protocol === "https:";
  } catch {
    return false;
  }
}

const ELEMENT_NODE = 1;
const TEXT_NODE = 3;

type MarkupNode = MarkupElement | MarkupText;

type MarkupText = {
  nodeType: typeof TEXT_NODE;
  textContent: string;
  childNodes: MarkupNode[];
  parentElement: MarkupElement | null;
};

type MarkupElement = {
  nodeType: typeof ELEMENT_NODE;
  tagName: string;
  childNodes: MarkupNode[];
  parentElement: MarkupElement | null;
  getAttribute: (name: string) => string | null;
};

const VOID_TAGS = new Set([
  "AREA",
  "BASE",
  "BR",
  "COL",
  "EMBED",
  "HR",
  "IMG",
  "INPUT",
  "LINK",
  "META",
  "PARAM",
  "SOURCE",
  "TRACK",
  "WBR",
]);

function decodeEntities(text: string): string {
  return text
    .replace(/&nbsp;/gi, "\u00a0")
    .replace(/&amp;/gi, "&")
    .replace(/&lt;/gi, "<")
    .replace(/&gt;/gi, ">")
    .replace(/&quot;/gi, '"')
    .replace(/&#39;|&apos;/gi, "'")
    .replace(/&#x([0-9a-f]+);/gi, (_, hex: string) =>
      String.fromCharCode(parseInt(hex, 16)),
    )
    .replace(/&#(\d+);/g, (_, dec: string) =>
      String.fromCharCode(Number(dec)),
    );
}

function parseAttributes(raw: string): Record<string, string> {
  const attrs: Record<string, string> = {};
  const pattern =
    /([^\s=/>]+)(?:\s*=\s*(?:"([^"]*)"|'([^']*)'|([^\s>]+)))?/g;
  let match: RegExpExecArray | null;
  while ((match = pattern.exec(raw))) {
    const name = match[1].toLowerCase();
    if (name === "/" || name === "") continue;
    attrs[name] = decodeEntities(match[2] ?? match[3] ?? match[4] ?? "");
  }
  return attrs;
}

function createElement(
  tagName: string,
  attrs: Record<string, string> = {},
  parent: MarkupElement | null = null,
): MarkupElement {
  return {
    nodeType: ELEMENT_NODE,
    tagName,
    childNodes: [],
    parentElement: parent,
    getAttribute: (name: string) =>
      Object.prototype.hasOwnProperty.call(attrs, name.toLowerCase())
        ? attrs[name.toLowerCase()]
        : null,
  };
}

function createText(text: string, parent: MarkupElement | null): MarkupText {
  return {
    nodeType: TEXT_NODE,
    textContent: text,
    childNodes: [],
    parentElement: parent,
  };
}

function parseHtmlBody(html: string): MarkupElement {
  const root = createElement("BODY");
  const stack: MarkupElement[] = [root];
  let index = 0;

  const current = () => stack[stack.length - 1];

  while (index < html.length) {
    if (html.startsWith("<!--", index)) {
      const end = html.indexOf("-->", index + 4);
      index = end === -1 ? html.length : end + 3;
      continue;
    }

    if (html[index] !== "<") {
      const nextTag = html.indexOf("<", index);
      const raw =
        nextTag === -1 ? html.slice(index) : html.slice(index, nextTag);
      current().childNodes.push(createText(decodeEntities(raw), current()));
      index = nextTag === -1 ? html.length : nextTag;
      continue;
    }

    const tagEnd = html.indexOf(">", index + 1);
    if (tagEnd === -1) {
      current().childNodes.push(createText(html.slice(index), current()));
      break;
    }

    const rawTag = html.slice(index + 1, tagEnd).trim();
    index = tagEnd + 1;

    if (rawTag.startsWith("!")) {
      continue;
    }

    if (rawTag.startsWith("/")) {
      const closing = rawTag.slice(1).trim().toUpperCase();
      for (let depth = stack.length - 1; depth > 0; depth -= 1) {
        if (stack[depth].tagName === closing) {
          stack.length = depth;
          break;
        }
      }
      continue;
    }

    const selfClosing = rawTag.endsWith("/");
    const nameMatch = rawTag.match(/^([^\s/>]+)/);
    if (!nameMatch) continue;
    const tagName = nameMatch[1].toUpperCase();
    const attrSource = rawTag.slice(nameMatch[1].length);
    const element = createElement(
      tagName,
      parseAttributes(attrSource),
      current(),
    );
    current().childNodes.push(element);

    if (!selfClosing && !VOID_TAGS.has(tagName)) {
      stack.push(element);
    }
  }

  return root;
}

function serializeChildren(node: MarkupNode): string {
  let output = "";
  for (const child of node.childNodes) {
    output += serializeNode(child);
  }
  return output;
}

function serializeList(
  element: MarkupElement,
  ordered: boolean,
  depth = 0,
): string {
  let output = "";
  let index = 1;
  const indent = "  ".repeat(depth);

  for (const child of element.childNodes) {
    if (child.nodeType !== ELEMENT_NODE) continue;
    if (child.tagName !== "LI") continue;

    let inline = "";
    let nested = "";
    for (const liChild of child.childNodes) {
      if (liChild.nodeType === ELEMENT_NODE) {
        if (liChild.tagName === "UL") {
          nested += serializeList(liChild, false, depth + 1);
        } else if (liChild.tagName === "OL") {
          nested += serializeList(liChild, true, depth + 1);
        } else {
          inline += serializeNode(liChild);
        }
      } else {
        inline += serializeNode(liChild);
      }
    }

    const marker = ordered ? `${index}. ` : "- ";
    output += `${indent}${marker}${inline.trim()}\n`;
    if (nested) output += nested;
    index += 1;
  }

  return output;
}

function serializeNode(node: MarkupNode): string {
  if (node.nodeType === TEXT_NODE) {
    return node.textContent.replace(/\u00a0/g, " ");
  }

  const element = node;
  const tag = element.tagName;
  const inner = () => serializeChildren(element);

  switch (tag) {
    case "BR":
      return "\n";
    case "STRONG":
    case "B": {
      const content = inner().trim();
      return content ? `**${content}**` : "";
    }
    case "EM":
    case "I": {
      const content = inner().trim();
      return content ? `*${content}*` : "";
    }
    case "U": {
      const content = inner().trim();
      return content ? `__${content}__` : "";
    }
    case "S":
    case "STRIKE":
    case "DEL": {
      const content = inner().trim();
      return content ? `~~${content}~~` : "";
    }
    case "CODE": {
      if (element.parentElement?.tagName === "PRE") {
        return inner();
      }
      const content = inner().trim();
      return content ? `\`${content}\`` : "";
    }
    case "PRE": {
      const content = inner().replace(/\n+$/, "");
      return content ? `\`\`\`\n${content}\n\`\`\`\n` : "";
    }
    case "A": {
      const href = element.getAttribute("href") ?? "";
      const content = inner().trim() || href;
      if (!href || !isSafeHttpUrl(href)) return content;
      return `[${content}](${href})`;
    }
    case "H1":
      return `# ${inner().trim()}\n\n`;
    case "H2":
      return `## ${inner().trim()}\n\n`;
    case "H3":
      return `### ${inner().trim()}\n\n`;
    case "H4":
    case "H5":
    case "H6":
      return `**${inner().trim()}**\n\n`;
    case "UL":
      return `${serializeList(element, false)}\n`;
    case "OL":
      return `${serializeList(element, true)}\n`;
    case "LI":
      return `${inner().trim()}\n`;
    case "BLOCKQUOTE": {
      const content = inner().trim();
      return content
        ? `${content
            .split("\n")
            .map((line) => `> ${line}`)
            .join("\n")}\n\n`
        : "";
    }
    case "P":
    case "DIV": {
      const content = inner();
      return content.trim() ? `${content.replace(/\n+$/, "")}\n\n` : "";
    }
    case "SCRIPT":
    case "STYLE":
    case "IFRAME":
      return "";
    default:
      return inner();
  }
}

export function htmlToDiscordMarkdown(html: string): string {
  if (!html) {
    return html;
  }

  const markdown = serializeChildren(parseHtmlBody(html));

  return markdown.replace(/\n{3,}/g, "\n\n").trim();
}

function escapeHtml(text: string): string {
  return text
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;")
    .replace(/"/g, "&quot;");
}

function inlineMarkdownToHtml(text: string): string {
  return text
    .replace(/\[([^\]]+)\]\((https?:\/\/[^\s)]+)\)/g, '<a href="$2">$1</a>')
    .replace(/`([^`]+)`/g, "<code>$1</code>")
    .replace(/\*\*([^*]+)\*\*/g, "<strong>$1</strong>")
    .replace(/__([^_]+)__/g, "<u>$1</u>")
    .replace(/~~([^~]+)~~/g, "<s>$1</s>")
    .replace(/\*([^*]+)\*/g, "<em>$1</em>")
    .replace(/(^|[^_\w])_([^_]+)_(?=[^_\w]|$)/g, "$1<em>$2</em>");
}

/**
 * Converts the Discord markdown subset back to HTML so existing messages can
 * be loaded into TinyMCE (edit flows) and rendered in preview panes.
 */
export function discordMarkdownToHtml(markdown: string): string {
  if (!markdown) {
    return "";
  }

  const lines = escapeHtml(markdown).split("\n");
  const htmlParts: string[] = [];
  let listBuffer: string[] = [];
  let listOrdered = false;
  let quoteBuffer: string[] = [];
  let codeBuffer: string[] | null = null;

  const flushList = () => {
    if (listBuffer.length === 0) return;
    const tag = listOrdered ? "ol" : "ul";
    htmlParts.push(
      `<${tag}>${listBuffer.map((item) => `<li>${item}</li>`).join("")}</${tag}>`,
    );
    listBuffer = [];
  };

  const flushQuote = () => {
    if (quoteBuffer.length === 0) return;
    htmlParts.push(
      `<blockquote>${quoteBuffer.map((line) => inlineMarkdownToHtml(line)).join("<br />")}</blockquote>`,
    );
    quoteBuffer = [];
  };

  for (const line of lines) {
    if (codeBuffer !== null) {
      if (line.trim() === "```") {
        htmlParts.push(`<pre><code>${codeBuffer.join("\n")}</code></pre>`);
        codeBuffer = null;
      } else {
        codeBuffer.push(line);
      }
      continue;
    }

    if (line.trim().startsWith("```")) {
      flushList();
      flushQuote();
      codeBuffer = [];
      continue;
    }

    const bulletMatch = line.match(/^(\s*)-\s+(.*)$/);
    const orderedMatch = line.match(/^(\s*)\d+\.\s+(.*)$/);

    if (bulletMatch) {
      flushQuote();
      if (listBuffer.length > 0 && listOrdered) flushList();
      listOrdered = false;
      listBuffer.push(inlineMarkdownToHtml(bulletMatch[2]));
      continue;
    }

    if (orderedMatch) {
      flushQuote();
      if (listBuffer.length > 0 && !listOrdered) flushList();
      listOrdered = true;
      listBuffer.push(inlineMarkdownToHtml(orderedMatch[2]));
      continue;
    }

    flushList();

    const headingMatch = line.match(/^(#{1,3})\s+(.*)$/);
    if (headingMatch) {
      flushQuote();
      const level = headingMatch[1].length;
      htmlParts.push(
        `<h${level}>${inlineMarkdownToHtml(headingMatch[2])}</h${level}>`,
      );
      continue;
    }

    const quoteMatch = line.match(/^&gt;\s+(.*)$/);
    if (quoteMatch) {
      quoteBuffer.push(quoteMatch[1]);
      continue;
    }

    flushQuote();

    if (line.trim() === "") {
      htmlParts.push('<p class="prose-spacer">&nbsp;</p>');
      continue;
    }

    htmlParts.push(`<p>${inlineMarkdownToHtml(line)}</p>`);
  }

  if (codeBuffer !== null) {
    htmlParts.push(`<pre><code>${codeBuffer.join("\n")}</code></pre>`);
  }

  flushList();
  flushQuote();

  return htmlParts.join("");
}

/** Substitutes template variables with sample values for preview panes. */
export function substituteVariables(
  text: string,
  values: Record<string, string>,
): string {
  let output = text;

  for (const [variable, value] of Object.entries(values)) {
    output = output.split(variable).join(value);
  }

  return output;
}
