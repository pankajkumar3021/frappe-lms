import type { Directive } from 'vue'
import { renderMath } from '@/utils/math'

// Plain text that may hold LaTeX formulas, such as quiz answer explanations.
// The value is set as text, never as HTML, so "x < 3" stays text; formulas in
// it are then rendered by KaTeX. Usage: v-math-text="value".
const render = (el: HTMLElement, value?: string | null) => {
	el.textContent = value ?? ''
	void renderMath(el)
}

const mathText: Directive<HTMLElement, string | null | undefined> = {
	mounted: (el, binding) => render(el, binding.value),
	updated: (el, binding) => {
		if (binding.value !== binding.oldValue) render(el, binding.value)
	},
}

export default mathText
