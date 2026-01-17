/**
 * HTML sanitization utilities using DOMPurify.
 * Prevents XSS attacks when rendering user-generated HTML content.
 */

import DOMPurify from 'dompurify';

/**
 * Sanitize HTML content for safe rendering.
 * Allows basic formatting tags (b, i, u, s, a) and removes potentially dangerous content.
 */
export function sanitizeHtml(html: string): string {
	if (typeof window === 'undefined') {
		// Server-side: strip all HTML tags as a fallback
		return html.replace(/<[^>]*>/g, '');
	}

	return DOMPurify.sanitize(html, {
		ALLOWED_TAGS: ['b', 'i', 'u', 's', 'strong', 'em', 'a', 'br', 'span'],
		ALLOWED_ATTR: ['href', 'target', 'rel', 'class'],
		ALLOW_DATA_ATTR: false
	});
}

/**
 * Extract plain text from HTML content safely.
 */
export function extractTextFromHtml(html: string): string {
	if (typeof window === 'undefined') {
		// Server-side: strip all HTML tags
		return html.replace(/<[^>]*>/g, '');
	}

	// Sanitize first, then extract text
	const sanitized = sanitizeHtml(html);
	const tempDiv = document.createElement('div');
	tempDiv.innerHTML = sanitized;
	return tempDiv.textContent || '';
}

/**
 * Validate and sanitize a URL for use in links.
 * Returns null if the URL is invalid or potentially dangerous.
 */
export function sanitizeUrl(url: string): string | null {
	if (!url) return null;

	try {
		const parsed = new URL(url, window.location.origin);
		// Only allow http, https, and mailto protocols
		if (['http:', 'https:', 'mailto:'].includes(parsed.protocol)) {
			return parsed.href;
		}
		return null;
	} catch {
		return null;
	}
}
