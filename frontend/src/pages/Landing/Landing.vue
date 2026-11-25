<template>
	<div id="top" class="lp-root" :style="brandStyle">
		<div v-if="content.promo" class="lp-promo">
			{{ content.promo }}
		</div>

		<LandingHeader
			:brand="brand"
			:branches="content.branches"
			:contact-phone="content.contact.phone"
		/>
		<LandingHero
			:hero="content.hero"
			:brand-name="brand.name"
			:branch-count="content.branches.length"
		/>

		<LandingCourses />

		<section id="test-series" class="lp-section scroll-mt-24">
			<div class="lp-container">
				<div class="lp-banner">
					<div class="flex min-w-0 flex-[1_1_460px] flex-col gap-4">
						<span class="lp-tag self-start">{{ __(testSeries.label) }}</span>
						<h2 class="lp-heading text-[clamp(1.9rem,3.4vw,2.5rem)] text-white">
							{{ __(testSeries.headline) }}
						</h2>
						<p class="text-[17px] leading-relaxed text-[#dbeafe]">
							{{ __(testSeries.text) }}
						</p>
						<a href="#contact" class="lp-btn-light self-start">{{
							__('Register for the test')
						}}</a>
					</div>
					<ul class="grid min-w-0 flex-[1_1_360px] grid-cols-3 gap-3.5">
						<li
							v-for="prize in testSeries.prizes"
							:key="prize.place"
							class="rounded-[18px] bg-white/[.12] px-4 py-5 text-center"
						>
							<span class="block text-sm text-[#dbeafe]">{{
								__(prize.place)
							}}</span>
							<span
								class="lp-heading mt-1.5 block text-[clamp(1.2rem,2.2vw,1.75rem)] text-white"
								>{{ prize.amount }}</span
							>
						</li>
					</ul>
				</div>
			</div>
		</section>

		<LandingBranches :branches="content.branches" />
		<LandingContact :contact="content.contact" />

		<footer class="lp-footer">
			<div class="lp-container flex flex-wrap justify-between gap-2">
				<span>© {{ brand.name }}</span>
				<a
					v-if="content.contact.email"
					:href="safeUrl(`mailto:${content.contact.email}`)"
					class="text-[#93c5fd]"
					>{{ content.contact.email }}</a
				>
			</div>
		</footer>
	</div>
</template>

<script setup lang="ts">
import { safeUrl } from '@/utils/safeUrl'
import { computed } from 'vue'
import { createResource } from 'frappe-ui'
import LandingHeader from '@/components/Landing/LandingHeader.vue'
import LandingHero from '@/components/Landing/LandingHero.vue'
import LandingCourses from '@/components/Landing/LandingCourses.vue'
import LandingBranches from '@/components/Landing/LandingBranches.vue'
import LandingContact from '@/components/Landing/LandingContact.vue'
import { sessionStore } from '@/stores/session'
import { testSeries } from '@/pages/Landing/content'
import type { LandingContent } from '@/pages/Landing/content'
import './landing.css'

const EMPTY: LandingContent = {
	enabled: false,
	brand: { name: '', logo: null, primary_colour: '' },
	promo: '',
	hero: { eyebrow: '', headline: '', lede: '' },
	slides: [],
	branches: [],
	contact: { phone: '', email: '', website: '' },
}

const landing = createResource({
	url: 'lms.lms.api.get_landing_content',
	auto: true,
})

const content = computed<LandingContent>(() => {
	const data = (landing.data as Partial<LandingContent> | undefined) || {}
	return {
		...EMPTY,
		...data,
		hero: { ...EMPTY.hero, ...(data.hero || {}) },
		contact: { ...EMPTY.contact, ...(data.contact || {}) },
		brand: { ...EMPTY.brand, ...(data.brand || {}) },
		slides: data.slides || [],
		branches: data.branches || [],
	}
})

const brand = computed(() => ({
	// A blank name in settings falls back to the site name.
	name: content.value.brand.name || sessionStore().brand.name || '',
	logo: logoUrl(content.value.brand.logo) || logoUrl(sessionStore().brand.logo),
}))

// The site logo from get_branding is a file record ({ file_url, … }), not a URL,
// while the landing settings give a plain URL. Accept either.
function logoUrl(value: unknown): string | null {
	if (typeof value === 'string') return value || null
	const fileUrl = (value as { file_url?: unknown } | null)?.file_url
	return typeof fileUrl === 'string' && fileUrl ? fileUrl : null
}

// The brand colour from settings sets the accent. The stylesheet's default applies when blank.
const brandStyle = computed(() => {
	const colour = content.value.brand.primary_colour
	if (!/^#[0-9a-fA-F]{6}$/.test(colour)) return {}
	const onAccent = readableOn(colour)
	return {
		'--lp-accent': colour,
		'--lp-on-accent': onAccent,
		// The test series banner has white text, so it takes the brand colour only when that colour is dark.
		...(onAccent === '#ffffff'
			? { '--lp-banner': colour }
			: // A light colour is unreadable as text on the pale hero, so text uses dark ink instead.
				{ '--lp-accent-text': '#111827' }),
	}
})

// Dark text on a light accent, white on a dark one, so the button text stays readable.
function readableOn(hex: string) {
	const [r, g, b] = [1, 3, 5].map(
		(i) => parseInt(hex.slice(i, i + 2), 16) / 255,
	)
	const luminance = 0.2126 * r + 0.7152 * g + 0.0722 * b
	return luminance > 0.55 ? '#000510' : '#ffffff'
}
</script>
