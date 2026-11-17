import { afterEach, describe, expect, it } from 'vitest'
import { showHomeAtSiteRoot } from '@/router'

function at(url: string) {
	window.history.replaceState({ current: '/' }, '', url)
}

describe('showHomeAtSiteRoot', () => {
	afterEach(() => at('/'))

	it('shows Home at the bare site root', () => {
		at('/lms/')
		showHomeAtSiteRoot({ name: 'Home' })
		expect(window.location.pathname).toBe('/')
	})

	it('keeps the query string and hash', () => {
		at('/lms/?ref=ad#courses')
		showHomeAtSiteRoot({ name: 'Home' })
		expect(window.location.pathname + window.location.search + window.location.hash).toBe(
			'/?ref=ad#courses',
		)
	})

	it('keeps the router state', () => {
		at('/lms/')
		showHomeAtSiteRoot({ name: 'Home' })
		expect(window.history.state).toEqual({ current: '/' })
	})

	it('leaves other pages under /lms', () => {
		at('/lms/courses')
		showHomeAtSiteRoot({ name: 'Courses' })
		expect(window.location.pathname).toBe('/lms/courses')
	})
})
