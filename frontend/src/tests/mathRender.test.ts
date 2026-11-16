import { describe, expect, it, vi } from 'vitest'
import { mount } from '@vue/test-utils'
import { defineComponent } from 'vue'
import { renderMath, hasMath } from '@/utils/math'

function host(html: string): HTMLElement {
	const el = document.createElement('div')
	el.innerHTML = html
	return el
}

describe('renderMath', () => {
	it('renders a $$ … $$ formula as display maths', async () => {
		const el = host('<p>Area: $$A = \\pi r^2$$</p>')
		await renderMath(el)
		expect(el.querySelector('.katex-display')).not.toBeNull()
		expect(el.textContent).not.toContain('$$')
	})

	it('renders a \\( … \\) formula inline', async () => {
		const el = host('<p>Since \\(a^2 + b^2 = c^2\\) holds</p>')
		await renderMath(el)
		expect(el.querySelector('.katex')).not.toBeNull()
		expect(el.querySelector('.katex-display')).toBeNull()
	})

	it('renders a \\[ … \\] formula as display maths', async () => {
		const el = host('<p>\\[x = \\frac{-b \\pm \\sqrt{b^2 - 4ac}}{2a}\\]</p>')
		await renderMath(el)
		expect(el.querySelector('.katex-display')).not.toBeNull()
	})

	it('leaves text with single dollar signs alone', async () => {
		const el = host('<p>The book costs $5 and the pen $10.</p>')
		const before = el.innerHTML
		await renderMath(el)
		expect(el.innerHTML).toBe(before)
		expect(hasMath(el.textContent)).toBe(false)
	})

	it('does not render inside code blocks', async () => {
		const el = host('<pre><code>$$x^2$$</code></pre>')
		await renderMath(el)
		expect(el.querySelector('.katex')).toBeNull()
		expect(el.textContent).toContain('$$x^2$$')
	})

	it('shows a broken formula instead of throwing', async () => {
		const el = host('<p>$$\\frac{1}{$$</p>')
		await expect(renderMath(el)).resolves.toBeUndefined()
	})

	it('accepts a missing element', async () => {
		await expect(renderMath(null)).resolves.toBeUndefined()
	})
})

describe('v-safe-html and formulas', () => {
	const Rich = defineComponent({
		props: {
			level: { type: String, required: true },
			html: { type: String, required: true },
		},
		template: `
			<div>
				<div v-if="level === 'rich'" class="target" v-safe-html:rich="html"></div>
				<div v-else class="target" v-safe-html:basic="html"></div>
			</div>
		`,
	})

	it('renders formulas in rich content', async () => {
		const wrapper = mount(Rich, {
			props: { level: 'rich', html: '<p>$$E = mc^2$$</p>' },
		})
		await vi.waitFor(() =>
			expect(wrapper.find('.target .katex').exists()).toBe(true),
		)
		wrapper.unmount()
	})

	it('leaves formulas as text in basic content', async () => {
		const wrapper = mount(Rich, {
			props: { level: 'basic', html: '<p>$$E = mc^2$$</p>' },
		})
		await new Promise((r) => setTimeout(r, 50))
		expect(wrapper.find('.target .katex').exists()).toBe(false)
		expect(wrapper.find('.target').text()).toContain('$$E = mc^2$$')
		wrapper.unmount()
	})
})
