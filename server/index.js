import Fastify from 'fastify';
import cors from '@fastify/cors';
import multipart from '@fastify/multipart';
import { createWriteStream, promises as fs } from 'fs';
import path from 'path';
import { fileURLToPath } from 'url';
import { v4 as uuidv4 } from 'uuid';
import unzipper from 'unzipper';
import * as cheerio from 'cheerio';
import { daleChallReadabilityScore, fleschKincaidGrade, fleschReadingEase, automatedReadabilityIndex, smogIndex } from 'text-readability';
import natural from 'natural';

const __filename = fileURLToPath(import.meta.url);
const __dirname = path.dirname(__filename);

const DATA_DIR = path.join(__dirname, 'data');
const BOOKS_DIR = path.join(DATA_DIR, 'books');
const ANALYSES_DIR = path.join(DATA_DIR, 'analyses');
await fs.mkdir(BOOKS_DIR, { recursive: true });
await fs.mkdir(ANALYSES_DIR, { recursive: true });

const fastify = Fastify({ logger: true });
await fastify.register(cors, { origin: true });
await fastify.register(multipart, { limits: { fileSize: 200 * 1024 * 1024 } });

fastify.get('/health', async () => ({ status: 'ok' }));

fastify.post('/upload', async (request, reply) => {
  const parts = request.parts();
  let fileInfo = null;
  for await (const part of parts) {
    if (part.type === 'file') {
      const { filename } = part;
      if (!filename || !filename.toLowerCase().endsWith('.epub')) {
        return reply.code(400).send({ error: 'Only .epub files are supported' });
      }
      const bookId = uuidv4();
      const outPath = path.join(BOOKS_DIR, `${bookId}.epub`);
      await new Promise((res, rej) => {
        const stream = createWriteStream(outPath);
        part.file.pipe(stream);
        stream.on('finish', res);
        stream.on('error', rej);
      });
      fileInfo = { book_id: bookId, filename };
    } else {
      // drain fields
      await part.toBuffer();
    }
  }
  if (!fileInfo) return reply.code(400).send({ error: 'No file uploaded' });
  return fileInfo;
});

async function extractTextFromEpub(epubPath) {
  // Unzip epub and extract text from xhtml/html files
  const directory = await unzipper.Open.file(epubPath);
  let combined = '';
  for (const entry of directory.files) {
    if (!entry.path.toLowerCase().endsWith('.xhtml') && !entry.path.toLowerCase().endsWith('.html')) continue;
    const content = await entry.buffer();
    const $ = cheerio.load(content.toString('utf-8'));
    $('script, style').remove();
    const text = $('body').text();
    combined += '\n' + text;
  }
  return combined.replace(/\s+/g, ' ').trim();
}

function extractKeywords(text, topK = 20) {
  const tokenizer = new natural.WordTokenizer();
  const sentences = text.split(/[.!?]+\s/).filter(Boolean);
  const tfidf = new natural.TfIdf();
  const docs = sentences.slice(0, 2000);
  for (const s of docs) tfidf.addDocument(tokenizer.tokenize(s).join(' '));
  const terms = {};
  tfidf.listTerms(0).forEach(t => { terms[t.term] = t.tfidf; });
  const sorted = Object.entries(terms)
    .filter(([term]) => term.length >= 3 && !/\d/.test(term))
    .sort((a, b) => b[1] - a[1])
    .slice(0, topK)
    .map(([term]) => term);
  return sorted;
}

function computeComplexity(text) {
  try {
    return {
      flesch_reading_ease: fleschReadingEase(text),
      flesch_kincaid_grade: fleschKincaidGrade(text),
      dale_chall_readability_score: daleChallReadabilityScore(text),
      smog_index: smogIndex(text),
      automated_readability_index: automatedReadabilityIndex(text),
      avg_sentence_length: (() => {
        const sentences = text.split(/[.!?]+\s/).filter(Boolean);
        const words = text.split(/\s+/).filter(Boolean);
        return sentences.length ? (words.length / sentences.length) : 0;
      })(),
      lexicon_count: text.split(/\b[\w']+\b/g).length,
    };
  } catch {
    return {};
  }
}

fastify.post('/scan/:bookId', async (request, reply) => {
  const { bookId } = request.params;
  const epubPath = path.join(BOOKS_DIR, `${bookId}.epub`);
  try {
    await fs.access(epubPath);
  } catch {
    return reply.code(404).send({ error: 'Book not found' });
  }
  const text = await extractTextFromEpub(epubPath);
  const keywords = extractKeywords(text);
  // crude named entities: proper-case sequences
  const names = Array.from(new Set((text.match(/\b[A-Z][a-z]+(?:\s+[A-Z][a-z]+){0,3}\b/g) || []).slice(0, 200).map(s => s.trim())));
  const result = {
    book_id: bookId,
    characters: names.slice(0, 25),
    top_keywords: keywords,
    complexity: computeComplexity(text),
  };
  await fs.writeFile(path.join(ANALYSES_DIR, `${bookId}.json`), JSON.stringify(result, null, 2), 'utf-8');
  return result;
});

fastify.get('/analysis/:bookId', async (request, reply) => {
  const { bookId } = request.params;
  const p = path.join(ANALYSES_DIR, `${bookId}.json`);
  try {
    const data = await fs.readFile(p, 'utf-8');
    return JSON.parse(data);
  } catch {
    return reply.code(404).send({ error: 'Analysis not found. Run /scan first.' });
  }
});

const PORT = process.env.PORT || 8080;
fastify.listen({ port: Number(PORT), host: '0.0.0.0' }).catch(err => {
  fastify.log.error(err);
  process.exit(1);
});