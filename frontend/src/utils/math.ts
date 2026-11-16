/**
 * Renders LaTeX formulas in an element with KaTeX.
 *
 * Recognised delimiters:
 *   $$ … $$  and  \[ … \]   display (block) formulas
 *   \( … \)                 inline formulas
 *
 * Single $ … $ is deliberately not recognised: ordinary text such as
 * "$5 and $10" would be read as a formula.
 *
 * KaTeX is loaded on first use, so pages without formulas do not download it.
 * Rendering runs on text the sanitizer has already accepted, and KaTeX escapes
 * what it outputs, so this adds no HTML from user content.
 */

export const MATH_DELIMITERS = [
	{ left: '$$', right: '$$', display: true },
	{ left: '\\[', right: '\\]', display: true },
	{ left: '\\(', right: '\\)', display: false },
]

const HAS_MATH = /\$\$|\\\[|\\\(/

type RenderMathInElement = (
	el: HTMLElement,
	options: Record<string, unknown>,
) => void

let loader: Promise<RenderMathInElement> | null = null

function loadKatex(): Promise<RenderMathInElement> {
	if (!loader) {
		loader = Promise.all([
			import('katex/contrib/auto-render'),
			import('katex/dist/katex.min.css'),
		]).then(([mod]) => mod.default as RenderMathInElement)
	}
	return loader
}

export function hasMath(text: string | null | undefined): boolean {
	return HAS_MATH.test(text || '')
}

export async function renderMath(
	el: HTMLElement | null | undefined,
): Promise<void> {
	if (!el || !hasMath(el.textContent)) return
	const renderMathInElement = await loadKatex()
	renderMathInElement(el, {
		delimiters: MATH_DELIMITERS,
		// A typo in a formula shows the source in red instead of breaking the page.
		throwOnError: false,
		ignoredTags: [
			'script',
			'noscript',
			'style',
			'textarea',
			'pre',
			'code',
			'option',
		],
	})
}
