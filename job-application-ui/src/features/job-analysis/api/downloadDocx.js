/**
 * downloadDocx.js
 *
 * Generates a Lebenslauf .docx entirely in the browser.
 * Uses dynamic ESM import — no CDN script tag needed in index.html.
 */

// ─── Dynamic loader ───────────────────────────────────────────────────────────
//
// Start the CDN fetch immediately at module-evaluation time (page load) so the
// Promise is already resolved by the time the user clicks the button.
// Chrome's user-gesture propagation survives awaiting an already-resolved
// Promise (microtask tick only), but NOT a live network fetch — that's what
// was triggering the download-permissions dialog before.

const _docxPromise = import('https://cdn.jsdelivr.net/npm/docx@8/+esm');
let _docx = null;

async function getDocx() {
  if (!_docx) _docx = await _docxPromise;
  return _docx;
}

const d = () => _docx;

// ─── Public entry point ───────────────────────────────────────────────────────

export async function downloadLebenslaufDocx(cvMarkdown, avatarUrl) {
  await getDocx();

  const candidateName = extractCandidateName(cvMarkdown);
  const filename = `Lebenslauf_${candidateName.replace(/\s+/g, '_')}.docx`;

  const blob = await generateDocx(cvMarkdown, avatarUrl || '');
  triggerDownload(blob, filename);
}

export async function downloadAnschreibenDocx(text) {
  await getDocx();
  const candidateName = extractCandidateName(text);
  const filename = `Anschreiben_${candidateName.replace(/\s+/g, '_')}.docx`;
  const blob = await generateAnschreiben(text);
  triggerDownload(blob, filename);
}

// ─── Design tokens ────────────────────────────────────────────────────────────

const FONT  = 'Calibri';
const COLOR = { accent: '1F4E79', name: '1A1A1A', body: '2B2B2B', muted: '6B6B6B' };
const PT    = n => Math.round(n * 2);

const MM   = v => Math.round(v * 1440 / 25.4);
const PG_W = MM(210);
const PG_H = MM(297);
const MAR  = MM(20);
const CW   = PG_W - 2 * MAR;

const PHOTO = {
  wMM: 25, hMM: 32,
  get wDXA() { return MM(this.wMM); },
  get wPX()  { return Math.round(this.wMM / 25.4 * 96); },
  get hPX()  { return Math.round(this.hMM / 25.4 * 96); },
};

const NAME_COL = CW - PHOTO.wDXA;

// ─── Markdown parser ──────────────────────────────────────────────────────────

function parseCV(md) {
  const usesH2 = /^## /m.test(md);

  const sectionTitle = line => {
    if (/^## /.test(line)) return line.slice(3).trim();
    if (!usesH2 && /^\*\*[^*]+\*\*\s*$/.test(line))
      return line.replace(/^\*\*/, '').replace(/\*\*\s*$/, '').trim();
    return null;
  };

  const isSubHeader = line => usesH2 && /^\*\*[^*]+\*\*\s*$/.test(line);

  const isEntry = line =>
    line.startsWith('**') &&
    (/\d{2}\.\d{4}/.test(line) ||
     /\d{4}\s*[–\-]\s*(?:\d{4}|heute|present)/i.test(line) ||
     line.includes('|'));

  const strip = s =>
    s.replace(/\*\*([^*]+)\*\*/g, '$1')
     .replace(/\[([^\]]+)\]\([^)]+\)/g, '$1')
     .trim();

  const parseEntry = line => {
    const dateRx = /(\d{2}\.\d{4}\s*[–\-]\s*(?:\d{2}\.\d{4}|heute|present)|\d{4}\s*[–\-]\s*(?:\d{4}|heute|present))/i;
    const dateM  = line.match(dateRx);
    const date   = dateM ? dateM[1].trim() : '';
    const rest   = line.replace(date, '').replace(/[|·\s]+$/, '').trim();
    const parts  = rest.split('|').map(p => strip(p).trim());
    if (parts.length >= 2) return { title: parts[0], org: parts[1], date };
    const full = strip(parts[0]);
    const di   = full.lastIndexOf(' · ');
    if (di > 0) return { title: full.slice(0, di).trim(), org: full.slice(di + 3).trim(), date };
    return { title: full, org: '', date };
  };

  const isContact = (line, idx) =>
    /@/.test(line) || /\+\d{2}/.test(line) ||
    /linkedin\.com|github\.com/i.test(line) ||
    (idx <= 5 && /·/.test(line) && !line.startsWith('**'));

  const lines    = md.split('\n');
  const header   = { name: '', subtitle: '', contacts: [] };
  const sections = [];
  let cur        = null;
  let curEntry   = null;
  let inHeader   = true;

  for (let i = 0; i < lines.length; i++) {
    const line = lines[i].trim();
    if (!line) { if (!inHeader) curEntry = null; continue; }

    const secTitle = sectionTitle(line);
    if (secTitle) {
      cur = { title: secTitle, items: [] }; sections.push(cur);
      curEntry = null; inHeader = false; continue;
    }

    if (inHeader) {
      if (line.startsWith('# '))                     { header.name = line.slice(2).trim(); continue; }
      if (!header.name)                              { header.name = strip(line);           continue; }
      if (!header.subtitle && !isContact(line, i))  { header.subtitle = strip(line);       continue; }
      header.contacts.push(line);
      continue;
    }

    if (!cur) continue;

    if (isSubHeader(line)) {
      cur.items.push({ type: 'subheader', text: line.replace(/\*\*/g, '').trim() });
      curEntry = null; continue;
    }

    if (isEntry(line)) {
      curEntry = { type: 'entry', ...parseEntry(line), details: [], bullets: [] };
      cur.items.push(curEntry); continue;
    }

    if (line.startsWith('- ')) {
      const text = line.slice(2).replace(/^[–—]\s*/, '').trim();
      if (curEntry) curEntry.bullets.push(text);
      else          cur.items.push({ type: 'bullet', text });
      continue;
    }

    const text = strip(line);
    if (curEntry) curEntry.details.push(text);
    else          cur.items.push({ type: 'para', text });
  }

  return { header, sections };
}

// ─── Paragraph builders ───────────────────────────────────────────────────────

const r = (text, o = {}) => new (d().TextRun)({ text, font: FONT, ...o });
const p = (children, o = {}) => new (d().Paragraph)({ children, ...o });

const nameP = name =>
  p([r(name, { bold: true, size: PT(20), color: COLOR.name })],
    { spacing: { before: 0, after: 80 } });

const subtitleP = text =>
  p([r(text, { size: PT(10), color: COLOR.muted, italics: true })],
    { spacing: { before: 0, after: 40 } });

const contactP = raw => {
  const text = raw.replace(/\[([^\]]+)\]\([^)]+\)/g, '$1').replace(/\*\*/g, '').trim();
  return p([r(text, { size: PT(9.5), color: COLOR.muted })],
    { spacing: { before: 0, after: 20 } });
};

const sectionHeaderP = title =>
  p([r(title.toUpperCase(), { bold: true, size: PT(10.5), color: COLOR.accent })], {
    spacing: { before: 220, after: 80 },
    border: { bottom: { style: d().BorderStyle.SINGLE, size: 8, color: COLOR.accent, space: 4 } },
  });

const entryP = ({ title, org, date }) => {
  const children = [r(title, { bold: true, size: PT(10), color: COLOR.body })];
  if (org)  children.push(r(` · ${org}`, { size: PT(10),  color: COLOR.body }));
  if (date) children.push(r(`\t${date}`, { size: PT(9.5), color: COLOR.muted, italics: true }));
  return p(children, {
    spacing: { before: 120, after: 40 },
    tabStops: [{ type: d().TabStopType.RIGHT, position: d().TabStopPosition.MAX }],
  });
};

const detailP = text =>
  p([r(text, { size: PT(9.5), color: COLOR.muted, italics: true })],
    { spacing: { before: 0, after: 30 } });

const subheaderP = text =>
  p([r(text, { bold: true, size: PT(10), color: COLOR.body })],
    { spacing: { before: 100, after: 30 } });

const bodyP = text =>
  p([r(text, { size: PT(10), color: COLOR.body })],
    { spacing: { before: 0, after: 60 } });

const bulletP = text =>
  new (d().Paragraph)({
    numbering: { reference: 'cv-bullets', level: 0 },
    spacing: { before: 20, after: 20 },
    children: [r(text, { size: PT(10), color: COLOR.body })],
  });

// ─── Header table ─────────────────────────────────────────────────────────────

function buildHeaderTable(header, imgData, imgType) {
  const nb   = { style: d().BorderStyle.NONE, size: 0, color: 'auto' };
  const noBS = { top: nb, bottom: nb, left: nb, right: nb, insideH: nb, insideV: nb };
  const leftChildren = [
    nameP(header.name),
    ...(header.subtitle ? [subtitleP(header.subtitle)] : []),
    ...header.contacts.map(contactP),
  ];

  const rightChildren = imgData
    ? [p([new (d().ImageRun)({
        type: imgType,
        data: imgData,
        transformation: { width: PHOTO.wPX, height: PHOTO.hPX },
        altText: { title: 'Photo', description: 'Profile photo', name: 'photo' },
      })], { alignment: d().AlignmentType.RIGHT, spacing: { before: 0, after: 0 } })]
    : [p([])];

  return new (d().Table)({
    width:        { size: CW, type: d().WidthType.DXA },
    columnWidths: [NAME_COL, PHOTO.wDXA],
    borders:      noBS,
    rows: [new (d().TableRow)({
      children: [
        new (d().TableCell)({
          borders: noBS,
          width: { size: NAME_COL, type: d().WidthType.DXA },
          verticalAlign: d().VerticalAlign.TOP,
          margins: { top: 0, bottom: 0, left: 0, right: 220 },
          children: leftChildren,
        }),
        new (d().TableCell)({
          borders: noBS,
          width: { size: PHOTO.wDXA, type: d().WidthType.DXA },
          verticalAlign: d().VerticalAlign.TOP,
          margins: { top: 0, bottom: 0, left: 0, right: 0 },
          children: rightChildren,
        }),
      ],
    })],
  });
}

// ─── Section builder ──────────────────────────────────────────────────────────

function buildSection(section) {
  const out = [sectionHeaderP(section.title)];
  for (const item of section.items) {
    switch (item.type) {
      case 'para':      out.push(bodyP(item.text));      break;
      case 'subheader': out.push(subheaderP(item.text)); break;
      case 'bullet':    out.push(bulletP(item.text));    break;
      case 'entry':
        out.push(entryP(item));
        item.details.forEach(dt => out.push(detailP(dt)));
        item.bullets.forEach(b  => out.push(bulletP(b)));
        break;
    }
  }
  return out;
}

// ─── Image crop helper ────────────────────────────────────────────────────────
//
// Center-crops imgData (Uint8Array) to exactly PHOTO.wPX × PHOTO.hPX so Word
// never has to scale with a mismatched ratio — i.e. object-fit:cover in canvas.

function cropToPhotoRatio(imgData) {
  return new Promise((resolve, reject) => {
    const url = URL.createObjectURL(new Blob([imgData], { type: 'image/jpeg' }));
    const img = new Image();
    img.onerror = reject;
    img.onload = () => {
      const tgtW = PHOTO.wPX;
      const tgtH = PHOTO.hPX;
      const tgtRatio = tgtW / tgtH;
      const srcRatio = img.naturalWidth / img.naturalHeight;

      let sx, sy, sw, sh;
      if (srcRatio > tgtRatio) {
        // source is wider → crop left and right
        sh = img.naturalHeight;
        sw = sh * tgtRatio;
        sx = (img.naturalWidth - sw) / 2;
        sy = 0;
      } else {
        // source is taller → crop top and bottom
        sw = img.naturalWidth;
        sh = sw / tgtRatio;
        sx = 0;
        sy = (img.naturalHeight - sh) / 2;
      }

      const canvas = document.createElement('canvas');
      canvas.width  = tgtW;
      canvas.height = tgtH;
      canvas.getContext('2d').drawImage(img, sx, sy, sw, sh, 0, 0, tgtW, tgtH);
      URL.revokeObjectURL(url);

      canvas.toBlob(
        blob => blob.arrayBuffer().then(buf => resolve(new Uint8Array(buf))),
        'image/jpeg',
        0.90,
      );
    };
    img.src = url;
  });
}

// ─── Document assembly ────────────────────────────────────────────────────────

async function generateDocx(cvMarkdown, avatarUrl) {
  const parsed = parseCV(cvMarkdown);

  let imgData = null;
  let imgType = 'jpg';
  if (avatarUrl && avatarUrl.startsWith('data:')) {
    const m = avatarUrl.match(/^data:image\/([a-z+]+);base64,(.+)$/s);
    if (m) {
      const binary = atob(m[2].replace(/\s/g, ''));
      const raw = new Uint8Array(binary.length);
      for (let i = 0; i < binary.length; i++) raw[i] = binary.charCodeAt(i);
      imgData = await cropToPhotoRatio(raw);   // always outputs JPEG, always exact ratio
    }
  }

  const children = [
    buildHeaderTable(parsed.header, imgData, imgType),
    ...parsed.sections.flatMap(buildSection),
  ];

  const doc = new (d().Document)({
    numbering: {
      config: [{
        reference: 'cv-bullets',
        levels: [{
          level: 0, format: d().LevelFormat.BULLET, text: '–',
          alignment: d().AlignmentType.LEFT,
          style: {
            paragraph: { indent: { left: 360, hanging: 220 } },
            run: { font: FONT, size: PT(10), color: COLOR.body },
          },
        }],
      }],
    },
    styles: {
      default: { document: { run: { font: FONT, size: PT(10), color: COLOR.body } } },
    },
    sections: [{
      properties: {
        page: {
          size:   { width: PG_W, height: PG_H },
          margin: { top: MAR, bottom: MAR, left: MAR, right: MAR },
        },
      },
      children,
    }],
  });

  return d().Packer.toBlob(doc);
}

// ─── Anschreiben parser ───────────────────────────────────────────────────────

function parseAnschreiben(text) {
  const lines = text.split('\n').map(l => l.trim());

  const dateRx    = /\w+,\s+\d+\.\s+\w+\s+\d{4}/;
  const salutRx   = /^Sehr geehrte/i;
  const closingRx = /^Mit freundlichen/i;
  const anlagenRx = /^Anlagen/i;

  const dateIdx    = lines.findIndex(l => dateRx.test(l));
  const salutIdx   = lines.findIndex(l => salutRx.test(l));
  const closingIdx = lines.findIndex(l => closingRx.test(l));
  const anlagenIdx = lines.findIndex(l => anlagenRx.test(l));

  // Subject: first **bold** line or line containing "Bewerbung" that comes after date
  const subjectIdx = lines.findIndex(
    (l, i) => i > dateIdx && (/^\*\*.*\*\*$/.test(l) || /Bewerbung/i.test(l))
  );

  // Sender: lines before the first blank gap that precedes the date
  const firstBlank = lines.slice(0, Math.max(dateIdx, 0)).findIndex(l => l === '');
  const senderEnd  = firstBlank > 0 ? firstBlank : dateIdx;
  const sender     = lines.slice(0, senderEnd).filter(Boolean);

  // Recipient: non-blank lines between sender block end and date line
  const recipient = lines.slice(senderEnd, dateIdx).filter(Boolean);

  const date       = dateIdx    >= 0 ? lines[dateIdx]                               : '';
  const subject    = subjectIdx >= 0 ? lines[subjectIdx].replace(/\*\*/g, '').trim() : '';
  const salutation = salutIdx   >= 0 ? lines[salutIdx]                              : '';

  // Body: lines between salutation and closing, grouped into paragraphs
  const body = (salutIdx >= 0 && closingIdx > salutIdx)
    ? chunkIntoParagraphs(lines.slice(salutIdx + 1, closingIdx))
    : [];

  const closing = closingIdx >= 0 ? lines[closingIdx] : '';

  // Sig name: first non-blank line after closing (before Anlagen)
  const sigEnd  = anlagenIdx >= 0 ? anlagenIdx : lines.length;
  const sigName = closingIdx >= 0
    ? (lines.slice(closingIdx + 1, sigEnd).find(l => l.length > 0) || '')
    : '';

  // Anlagen items — strip leading dash if present
  const anlagen = anlagenIdx >= 0
    ? lines.slice(anlagenIdx + 1).filter(l => l.length > 0).map(l => l.replace(/^[-–]\s*/, '').trim())
    : [];

  return { sender, recipient, date, subject, salutation, body, closing, sigName, anlagen };
}

function chunkIntoParagraphs(lines) {
  const paras = [];
  let cur = [];
  for (const line of lines) {
    if (line === '') {
      if (cur.length) { paras.push(cur.join(' ')); cur = []; }
    } else {
      cur.push(line);
    }
  }
  if (cur.length) paras.push(cur.join(' '));
  return paras;
}

// ─── Anschreiben document assembly ───────────────────────────────────────────

async function generateAnschreiben(text) {
  const { sender, recipient, date, subject, salutation, body, closing, sigName, anlagen } =
    parseAnschreiben(text);

  // Local shorthand builders — 11pt body, no accent colours
  const rn  = (t, o = {}) => new (d().TextRun)({ text: t, font: FONT, size: PT(11), ...o });
  const lp  = (t, o = {}) => new (d().Paragraph)({
    children: [rn(t, o)],
    spacing:  { before: 0, after: 80 },
  });
  const blk = () => new (d().Paragraph)({ children: [], spacing: { before: 0, after: 80 } });

  const children = [
    // Sender address — small, muted
    ...sender.map(s => new (d().Paragraph)({
      children: [rn(s, { size: PT(9), color: COLOR.muted })],
      spacing:  { before: 0, after: 20 },
    })),
    blk(),

    // Recipient block
    ...recipient.map(r => lp(r, { color: COLOR.body })),
    blk(),

    // Date — right-aligned
    new (d().Paragraph)({
      alignment: d().AlignmentType.RIGHT,
      children:  [rn(date, { color: COLOR.body })],
      spacing:   { before: 0, after: 160 },
    }),

    // Subject — bold (omit paragraph entirely if empty)
    ...(subject ? [new (d().Paragraph)({
      children: [rn(subject, { bold: true, color: COLOR.body })],
      spacing:  { before: 0, after: 160 },
    })] : []),

    // Salutation
    lp(salutation, { color: COLOR.body }),
    blk(),

    // Body paragraphs
    ...body.map(para => new (d().Paragraph)({
      children: [rn(para, { color: COLOR.body })],
      spacing:  { before: 0, after: 120 },
    })),

    // Closing
    lp(closing, { color: COLOR.body }),

    // Two blank lines = signature space
    blk(),
    blk(),

    // Signer name
    lp(sigName, { color: COLOR.body }),
  ];

  // Anlagen block (optional)
  if (anlagen.length > 0) {
    children.push(blk());
    children.push(new (d().Paragraph)({
      children: [rn('Anlagen', { bold: true, color: COLOR.body })],
      spacing:  { before: 0, after: 60 },
    }));
    anlagen.forEach(item => children.push(lp(item, { color: COLOR.body })));
  }

  const doc = new (d().Document)({
    styles: {
      default: { document: { run: { font: FONT, size: PT(11), color: COLOR.body } } },
    },
    sections: [{
      properties: {
        page: {
          size:   { width: PG_W, height: PG_H },
          margin: { top: MAR, bottom: MAR, left: MM(25), right: MAR }, // DIN 5008: 25mm left
        },
      },
      children,
    }],
  });

  return d().Packer.toBlob(doc);
}

// ─── Helpers ──────────────────────────────────────────────────────────────────

function extractCandidateName(markdown) {
  const firstLine = markdown
    .split('\n')
    .map(l => l.replace(/^#+ /, '').trim())
    .find(l => l.length > 0);
  return firstLine || 'Kandidat';
}

function triggerDownload(blob, filename) {
  const url = URL.createObjectURL(blob);
  const a   = document.createElement('a');
  a.href = url; a.download = filename;
  document.body.appendChild(a);
  a.click();
  document.body.removeChild(a);
  URL.revokeObjectURL(url);
}
