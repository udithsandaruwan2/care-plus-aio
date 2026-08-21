/**
 * Deterministic signed feature-hashing embedder (Step 98).
 * Byte-parity with ``apps.matching.embeddings.HashEmbedder`` (Python blake2b).
 */

import { blake2b } from '@noble/hashes/blake2.js';

/** Must match ``apps.matching.models.EMBEDDING_DIM``. */
export const EMBEDDING_DIM = 768;

const TOKEN_RE = /[a-z0-9\u0d80-\u0dff\u0b80-\u0bff]+/gi;

function tokenizeText(text: string): string[] {
  const lower = text.toLowerCase();
  return lower.match(TOKEN_RE) ?? [];
}

function blakeDigest8(token: string): Uint8Array {
  return blake2b(new TextEncoder().encode(token), { dkLen: 8 });
}

function littleEndianU32(bytes: Uint8Array, offset = 0): number {
  return (
    (bytes[offset]! |
      (bytes[offset + 1]! << 8) |
      (bytes[offset + 2]! << 16) |
      (bytes[offset + 3]! << 24)) >>>
    0
  );
}

/** Flatten a caregiver-like profile into the document we embed (Python ``profile_to_text``). */
export function profileToText(profile: {
  specialties?: string[] | null;
  certifications?: string[] | null;
  languages?: string[] | null;
  care_levels?: string[] | null;
  bio?: string | null;
  display_name?: string | null;
}): string {
  const parts = [
    (profile.specialties || []).join(' '),
    (profile.certifications || []).join(' '),
    (profile.languages || []).join(' '),
    (profile.care_levels || []).join(' '),
    profile.bio || '',
    profile.display_name || '',
  ];
  return parts.filter(Boolean).join(' ').trim().toLowerCase();
}

/** Build a query string from structured intent (Python ``intent_to_text``). */
export function intentToText(input: {
  condition?: string;
  language?: string;
  care_level?: string;
  extra?: string;
}): string {
  return [input.condition, input.language, input.care_level, input.extra]
    .filter(Boolean)
    .join(' ')
    .trim()
    .toLowerCase();
}

function l2Normalize(mat: Float32Array[], dim: number): Float32Array[] {
  return mat.map((row) => {
    let sum = 0;
    for (let i = 0; i < dim; i++) sum += row[i]! * row[i]!;
    const norm = Math.max(Math.sqrt(sum), 1e-12);
    const out = new Float32Array(dim);
    for (let i = 0; i < dim; i++) out[i] = row[i]! / norm;
    return out;
  });
}

/**
 * Embed texts with signed feature hashing into ``EMBEDDING_DIM`` dims.
 * Returns L2-normalized Float32Array rows (length = texts.length).
 */
export function hashEmbed(texts: string[], dim: number = EMBEDDING_DIM): Float32Array[] {
  const rows: Float32Array[] = texts.map(() => new Float32Array(dim));
  for (let i = 0; i < texts.length; i++) {
    const row = rows[i]!;
    for (const tok of tokenizeText(texts[i] ?? '')) {
      const digest = blakeDigest8(tok);
      const idx = littleEndianU32(digest, 0) % dim;
      const sign = digest[4]! % 2 === 0 ? 1.0 : -1.0;
      row[idx]! += sign;
    }
  }
  return l2Normalize(rows, dim);
}

export class HashEmbedder {
  readonly dim = EMBEDDING_DIM;

  embed(texts: string[]): Float32Array[] {
    return hashEmbed(texts, this.dim);
  }
}

/** Cosine / inner-product for L2-normalized vectors. */
export function dot(a: Float32Array | number[], b: Float32Array | number[]): number {
  const n = Math.min(a.length, b.length);
  let s = 0;
  for (let i = 0; i < n; i++) s += Number(a[i]) * Number(b[i]);
  return s;
}
