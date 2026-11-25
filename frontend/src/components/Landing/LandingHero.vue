<template>
	<section class="lp-hero">
		<div
			class="lp-container flex flex-wrap items-start gap-10 pt-8 lg:flex-nowrap"
		>
			<div
				class="flex min-w-0 flex-[1_1_480px] flex-col gap-7 pb-8 pt-6 lg:pb-32"
			>
				<h1 class="lp-hero-title">
					{{ eyebrow }}<br />
					<span class="lp-hero-accent">{{ headline }}</span>
				</h1>
				<p class="max-w-xl text-lg leading-relaxed text-[var(--lp-body)]">
					{{ lede }}
				</p>
				<dl class="lp-facts">
					<div v-for="fact in facts" :key="fact.label" class="lp-fact">
						<dt class="order-2 mt-1 text-[15px] text-[var(--lp-caption)]">
							{{ fact.label }}
						</dt>
						<dd class="lp-heading order-1 text-[clamp(1.35rem,2vw,1.75rem)]">
							{{ fact.value }}
						</dd>
					</div>
				</dl>
				<div class="flex flex-wrap gap-3">
					<a href="#contact" class="lp-btn-primary lp-btn-lg">{{
						__('Enrol Now')
					}}</a>
					<a href="#test-series" class="lp-btn-outline lp-btn-lg">{{
						__('Free scholarship test')
					}}</a>
				</div>
			</div>

			<div class="min-w-0 flex-none pb-8 max-lg:w-full lg:pb-28">
				<img
					:src="safeUrl(studentPhoto)"
					:alt="__('A smiling student in a blue T-shirt, holding a notebook')"
					class="lp-hero-photo"
				/>
			</div>

			<div
				id="why"
				class="flex min-w-0 flex-[1_1_340px] scroll-mt-24 flex-col gap-3.5 pb-8 pt-6 lg:max-w-[340px] lg:pb-28"
			>
				<h2 class="lp-heading mb-1 text-[32px]">
					{{ __('Why {0}?').format(brandName) }}
				</h2>
				<ul class="flex flex-col gap-3.5">
					<li v-for="reason in whyUs" :key="reason.title" class="lp-reason">
						<span class="lp-icon-tile" aria-hidden="true">
							<svg
								width="22"
								height="22"
								viewBox="0 0 24 24"
								fill="none"
								stroke="currentColor"
								stroke-width="1.8"
								stroke-linecap="round"
								stroke-linejoin="round"
							>
								<path :d="reason.icon" />
							</svg>
						</span>
						<span class="flex min-w-0 flex-col gap-1">
							<h3 class="lp-heading text-lg">{{ __(reason.title) }}</h3>
							<span class="text-sm leading-relaxed text-[var(--lp-caption)]">{{
								__(reason.text)
							}}</span>
						</span>
					</li>
				</ul>
			</div>
		</div>

		<div id="programmes" class="lp-container lp-programmes">
			<a
				v-for="programme in programmes"
				:key="programme.name"
				href="#courses"
				class="lp-programme"
			>
				<span :class="['lp-programme-icon', `is-${programme.tone}`]">
					<svg
						width="28"
						height="28"
						viewBox="0 0 24 24"
						fill="none"
						stroke="currentColor"
						stroke-width="1.8"
						stroke-linecap="round"
						stroke-linejoin="round"
						aria-hidden="true"
					>
						<path :d="programme.icon" />
					</svg>
				</span>
				<span class="min-w-0 flex-1">
					<span class="lp-heading block text-[21px] leading-tight">{{
						__(programme.name)
					}}</span>
					<span class="lp-class-detail mt-1 block">{{
						__(programme.classes)
					}}</span>
				</span>
				<span class="lp-arrow-dot" aria-hidden="true">
					<svg
						width="14"
						height="14"
						viewBox="0 0 24 24"
						fill="none"
						stroke="currentColor"
						stroke-width="3"
						stroke-linecap="round"
						stroke-linejoin="round"
					>
						<path d="M9 6l6 6-6 6" />
					</svg>
				</span>
			</a>
		</div>
	</section>
</template>

<script setup lang="ts">
import { safeUrl } from '@/utils/safeUrl'
import { computed } from 'vue'
import studentPhoto from '@/assets/images/landing-student.jpg'
import {
	heroDefaults,
	heroFacts,
	programmes,
	whyUs,
} from '@/pages/Landing/content'
import type { LandingContent } from '@/pages/Landing/content'

const props = defineProps<{
	hero: LandingContent['hero']
	brandName: string
	branchCount: number
}>()

// Values from LMS Settings win; the defaults fill in what is left blank.
const eyebrow = computed(() => props.hero.eyebrow || __(heroDefaults.eyebrow))
const headline = computed(
	() => props.hero.headline || __(heroDefaults.headline),
)
const lede = computed(() => props.hero.lede || __(heroDefaults.lede))

const facts = computed(() => {
	const list = heroFacts.map((fact) => ({
		value: __(fact.value),
		label: __(fact.label),
	}))
	if (props.branchCount) {
		list.push({
			value: String(props.branchCount),
			label:
				props.branchCount === 1
					? __('Classroom branch')
					: __('Classroom branches'),
		})
	}
	return list
})
</script>
