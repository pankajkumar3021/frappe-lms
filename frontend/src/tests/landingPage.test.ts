import { describe, expect, it, vi, beforeEach } from 'vitest'
import { config, mount, flushPromises } from '@vue/test-utils'
import Landing from '@/pages/Landing/Landing.vue'

// main.js registers __ on the app; the tests mount without it.
config.global.mocks = {
	...config.global.mocks,
	__: (message: string) =>
		/{\d+}/.test(message)
			? {
					format: (...args: string[]) =>
						message.replace(/{(\d+)}/g, (_, i) => args[Number(i)]),
				}
			: message,
}

const session = vi.hoisted(() => ({
	brand: { name: 'Site Name', logo: null as unknown },
}))

const landing = vi.hoisted(() => ({
	courses: [] as Array<Record<string, unknown>>,
	content: {} as Record<string, unknown>,
}))

vi.mock('frappe-ui', () => ({
	Button: {
		props: ['route', 'variant', 'theme'],
		emits: ['click'],
		template:
			'<button type="button" @click="$emit(\'click\')"><slot /></button>',
	},
	createResource: (opts: { url: string }) => ({
		...opts,
		get data() {
			return opts.url === 'lms.lms.api.get_landing_content'
				? landing.content
				: landing.courses
		},
		loading: false,
		fetch: vi.fn(),
	}),
}))

vi.mock('@/stores/session', () => ({
	sessionStore: () => session,
}))

const sampleCourses = [
	{
		name: 'maths-a',
		title: 'Maths Foundation',
		short_introduction: 'Maths',
		paid_course: 1,
		delivery: 'offline',
		image: null,
	},
	{
		name: 'physics-s',
		title: 'Self Paced Physics',
		short_introduction: 'Physics',
		paid_course: 0,
		delivery: 'online',
		image: null,
	},
	{
		name: 'chem-a',
		title: 'Chemistry Batch',
		short_introduction: 'Chem',
		paid_course: 0,
		delivery: 'offline',
		image: null,
	},
]

const sampleContent = {
	enabled: true,
	brand: { name: 'Test Institute', logo: null, primary_colour: '#123456' },
	promo: 'Promo line for the test institute.',
	hero: {
		eyebrow: 'Eyebrow here',
		headline: 'Headline here',
		lede: 'Lede here',
	},
	slides: [
		{
			eyebrow: 'One',
			title: 'Slide one',
			text: 'Body one',
			cta: { label: 'Go one', href: '/courses' },
		},
		{
			eyebrow: 'Two',
			title: 'Slide two',
			text: 'Body two',
			cta: { label: 'Go two', href: '#contact' },
		},
		{
			eyebrow: 'Three',
			title: 'Slide three',
			text: 'Body three',
			cta: { label: '', href: '' },
		},
	],
	branches: [
		{
			label: 'Main Campus',
			name: 'Main Branch',
			address: 'Main street 1',
			phone: '+91 1111111111',
		},
		{
			label: 'Second Campus',
			name: 'Second Branch',
			address: 'Second street 2',
			phone: '+11 2222222',
		},
	],
	contact: {
		phone: '+91 7903466927',
		email: 'info@example.com',
		website: 'https://example.com',
	},
}

function mountLanding() {
	return mount(Landing, { attachTo: document.body })
}

beforeEach(() => {
	session.brand = { name: 'Site Name', logo: null }
	landing.courses = sampleCourses
	landing.content = sampleContent
	document.body.innerHTML = ''
})

describe('Landing page', () => {
	it('shows the configured brand, hero and Login, and the course cards with labels', async () => {
		const wrapper = mountLanding()
		await flushPromises()

		expect(wrapper.text()).toContain('Test Institute')
		expect(wrapper.text()).toContain('Eyebrow here')
		expect(wrapper.text()).toContain('Headline here')
		expect(wrapper.text()).toContain('Lede here')
		expect(wrapper.find('a[href="/login"]').text()).toBe('Login')
		expect(wrapper.text()).toContain('Maths Foundation')
		expect(wrapper.text()).toContain('Self Paced Physics')
		expect(wrapper.text()).toContain('Online self-paced')
		wrapper.unmount()
	})

	it('filters courses by delivery and sets aria-pressed on the active tab', async () => {
		const wrapper = mountLanding()
		await flushPromises()

		const offlineTab = wrapper
			.findAll('button')
			.find((b) => b.text() === 'Offline batch')!
		await offlineTab.trigger('click')

		expect(offlineTab.attributes('aria-pressed')).toBe('true')
		expect(wrapper.text()).toContain('Maths Foundation')
		expect(wrapper.text()).toContain('Chemistry Batch')
		expect(wrapper.text()).not.toContain('Self Paced Physics')
		wrapper.unmount()
	})

	it('shows every configured branch and phone, and no fee amounts', async () => {
		const wrapper = mountLanding()
		await flushPromises()

		for (const branch of sampleContent.branches) {
			expect(wrapper.text()).toContain(branch.label)
			expect(wrapper.text()).toContain(branch.phone)
		}
		// The test series prizes are the only rupee amounts on the page.
		const prizes = wrapper.find('#test-series ul').text()
		expect(prizes).toContain('₹50,000')
		expect(wrapper.text().replace(prizes, '')).not.toMatch(/₹/)
		wrapper.unmount()
	})

	it('applies the configured primary colour to the page', async () => {
		const wrapper = mountLanding()
		await flushPromises()

		expect(wrapper.find('.lp-root').attributes('style')).toContain(
			'--lp-accent: #123456',
		)
		wrapper.unmount()
	})

	it('copy falls back to selecting the number when the clipboard refuses', async () => {
		Object.defineProperty(navigator, 'clipboard', {
			value: { writeText: vi.fn().mockRejectedValue(new Error('refused')) },
			configurable: true,
		})
		const wrapper = mountLanding()
		await flushPromises()

		const copy = wrapper.findAll('button').find((b) => b.text() === 'Copy')!
		await copy.trigger('click')
		await flushPromises()

		expect(wrapper.findAll('button').some((b) => b.text() === 'Ctrl+C')).toBe(
			true,
		)
		expect(window.getSelection()?.toString()).toContain('+91 7903466927')
		wrapper.unmount()
	})

	it('the navigation has the programmes menu and the section links', async () => {
		const wrapper = mountLanding()
		await flushPromises()

		const nav = wrapper.find('nav')
		expect(nav.findAll('button').map((b) => b.text())).toEqual([
			'Classroom Programmes',
			'Online Courses',
		])
		const labels = nav.findAll('a').map((a) => a.text())
		for (const label of [
			'Test Series',
			'Study Material',
			'Scholarships',
			'Branches',
			'Contact',
		]) {
			expect(labels.some((text) => text.startsWith(label))).toBe(true)
		}
		wrapper.unmount()
	})

	it('Classroom Programmes opens and closes the list of courses offered', async () => {
		const wrapper = mountLanding()
		await flushPromises()

		const toggle = wrapper.find('nav button')
		expect(wrapper.find('#lp-classroom-menu').exists()).toBe(false)
		expect(toggle.attributes('aria-expanded')).toBe('false')

		await toggle.trigger('click')
		const menu = wrapper.find('#lp-classroom-menu')
		expect(toggle.attributes('aria-expanded')).toBe('true')
		expect(menu.text()).toContain('Courses offered by Test Institute')
		expect(menu.findAll('li')).toHaveLength(9)
		expect(menu.text()).toContain('IIT-JEE / NEET Rank Booster')
		expect(menu.text()).toContain('Class 11–12 Science (PCM / PCB)')

		await wrapper.find('[aria-label="Close courses"]').trigger('click')
		expect(wrapper.find('#lp-classroom-menu').exists()).toBe(false)
		wrapper.unmount()
	})

	it('Online Courses opens the online course list with the mobile app note', async () => {
		const wrapper = mountLanding()
		await flushPromises()

		const [classroom, online] = wrapper.find('nav').findAll('button')
		await online.trigger('click')
		const menu = wrapper.find('#lp-online-menu')
		expect(online.attributes('aria-expanded')).toBe('true')
		expect(menu.text()).toContain('Online courses by Test Institute')
		expect(menu.text()).toContain(
			'Live classes are taken on our Test Institute mobile app.',
		)
		// Only the self-paced course; offline batches stay in the classroom list.
		const items = menu.findAll('li')
		expect(items).toHaveLength(1)
		expect(items[0].text()).toContain('Self Paced Physics')
		expect(items[0].text()).toContain('Free · Online')
		expect(items[0].find('a').attributes('href')).toBe('/lms/courses/physics-s')

		// Opening the other menu swaps the panel instead of stacking two.
		await classroom.trigger('click')
		expect(wrapper.find('#lp-online-menu').exists()).toBe(false)
		expect(wrapper.find('#lp-classroom-menu').exists()).toBe(true)
		expect(online.attributes('aria-expanded')).toBe('false')
		wrapper.unmount()
	})

	it('the programme cards show bold class details and the full Rank Booster name', async () => {
		const wrapper = mountLanding()
		await flushPromises()

		const cards = wrapper.findAll('#programmes a')
		expect(cards.map((c) => c.text())).toEqual([
			expect.stringContaining('Foundation'),
			expect.stringContaining('Pre-Board'),
			expect.stringContaining('Launch Pad'),
			expect.stringContaining('IIT-JEE / NEET Rank Booster'),
		])
		expect(cards[0].find('.lp-class-detail').text()).toBe(
			'Class 5–8 · Olympiad',
		)
		wrapper.unmount()
	})

	it('the branch pill moves to the next branch and the call button follows it', async () => {
		const wrapper = mountLanding()
		await flushPromises()

		const pill = wrapper.find('[aria-label="Change branch"]')
		expect(pill.text()).toContain('Main Campus')
		expect(wrapper.find('a[href^="tel:"]').attributes('href')).toBe(
			'tel:+911111111111',
		)

		await pill.trigger('click')
		expect(pill.text()).toContain('Second Campus')
		expect(wrapper.find('a[href^="tel:"]').attributes('href')).toBe(
			'tel:+112222222',
		)

		await pill.trigger('click')
		expect(pill.text()).toContain('Main Campus')
		wrapper.unmount()
	})

	it('the hero shows the why-us list beside the photo and counts the branches', async () => {
		const wrapper = mountLanding()
		await flushPromises()

		const why = wrapper.find('#why')
		expect(why.find('h2').text()).toBe('Why Test Institute?')
		expect(why.findAll('li')).toHaveLength(4)
		expect(wrapper.find('.lp-hero img').attributes('alt')).toBeTruthy()
		expect(wrapper.find('.lp-facts').text()).toContain('2')
		expect(wrapper.find('.lp-facts').text()).toContain('Classroom branches')
		wrapper.unmount()
	})

	it('falls back to the default hero copy when the settings leave it blank', async () => {
		landing.content = {
			...sampleContent,
			hero: { eyebrow: '', headline: '', lede: '' },
		}
		const wrapper = mountLanding()
		await flushPromises()

		expect(wrapper.find('h1').text()).toContain('Building your foundation')
		expect(wrapper.find('h1').text()).toContain('for a brighter future')
		wrapper.unmount()
	})

	it('a light brand colour leaves the white-text banner on its default blue', async () => {
		landing.content = {
			...sampleContent,
			brand: { ...sampleContent.brand, primary_colour: '#fde68a' },
		}
		const wrapper = mountLanding()
		await flushPromises()

		const style = wrapper.find('.lp-root').attributes('style')
		expect(style).toContain('--lp-accent: #fde68a')
		expect(style).not.toContain('--lp-banner')
		expect(style).toContain('--lp-accent-text: #111827')
		wrapper.unmount()
	})

	it('shows the site logo when the session gives it as a file record', async () => {
		// get_branding returns the logo as { file_name, file_size, file_url }.
		session.brand = {
			name: 'Site Name',
			logo: {
				file_name: 'seal.png',
				file_size: 10,
				file_url: '/files/seal.png',
			},
		}
		const wrapper = mountLanding()
		await flushPromises()

		expect(wrapper.find('header.lp-nav').exists()).toBe(true)
		expect(wrapper.find('.lp-logo img').attributes('src')).toBe(
			'/files/seal.png',
		)
		expect(wrapper.find('a[href="/login"]').exists()).toBe(true)
		wrapper.unmount()
	})
})
