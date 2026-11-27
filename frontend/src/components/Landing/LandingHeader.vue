<template>
	<header class="lp-nav">
		<div class="lp-container pt-3">
			<div class="flex flex-wrap items-center justify-between gap-4">
				<div class="flex min-w-0 flex-wrap items-center gap-4">
					<a href="#top" class="lp-logo">
						<img
							v-if="brand.logo"
							:src="safeUrl(brand.logo)"
							alt=""
							class="h-10 w-auto max-w-[160px] object-contain"
						/>
						<span v-else class="lp-logo-mark" aria-hidden="true">{{
							brand.name.charAt(0)
						}}</span>
						<span class="truncate">{{ brand.name }}</span>
					</a>
					<button
						v-if="branches.length"
						type="button"
						class="lp-branch-pill"
						:aria-label="__('Change branch')"
						@click="nextBranch"
					>
						<svg
							width="16"
							height="16"
							viewBox="0 0 24 24"
							fill="none"
							stroke="currentColor"
							stroke-width="2"
							stroke-linecap="round"
							stroke-linejoin="round"
							aria-hidden="true"
						>
							<path d="M12 21s-7-6.2-7-11a7 7 0 0 1 14 0c0 4.8-7 11-7 11z" />
							<circle cx="12" cy="10" r="2.5" />
						</svg>
						<span class="truncate">{{ branchName }}</span>
						<span class="font-semibold text-[var(--lp-accent-text)]">{{
							__('Change')
						}}</span>
					</button>
				</div>

				<div class="flex items-center gap-3">
					<a
						v-if="phone"
						:href="safeUrl(`tel:${phone.replace(/[^\d+]/g, '')}`)"
						class="lp-call"
						:aria-label="__('Call {0}').format(phone)"
					>
						<svg
							width="20"
							height="20"
							viewBox="0 0 24 24"
							fill="none"
							stroke="currentColor"
							stroke-width="2"
							stroke-linecap="round"
							stroke-linejoin="round"
							aria-hidden="true"
						>
							<path
								d="M22 16.9v3a2 2 0 0 1-2.2 2 19.8 19.8 0 0 1-8.6-3.1 19.5 19.5 0 0 1-6-6A19.8 19.8 0 0 1 2.1 4.2 2 2 0 0 1 4.1 2h3a2 2 0 0 1 2 1.7c.1.9.4 1.8.7 2.7a2 2 0 0 1-.5 2.1L8 9.8a16 16 0 0 0 6 6l1.3-1.3a2 2 0 0 1 2.1-.4c.9.3 1.8.6 2.7.7a2 2 0 0 1 1.7 2z"
							/>
						</svg>
					</a>
					<a href="/login" class="lp-btn-outline hidden sm:inline-flex">{{
						__('Login')
					}}</a>
					<a href="/login" class="lp-btn-primary hidden sm:inline-flex">{{
						__('Register')
					}}</a>
					<button
						type="button"
						class="lp-menu-button xl:hidden"
						:aria-expanded="String(menuOpen)"
						aria-controls="lp-mobile-menu"
						@click="menuOpen = !menuOpen"
					>
						<span class="sr-only">{{
							menuOpen ? __('Close menu') : __('Open menu')
						}}</span>
						<span aria-hidden="true">{{ menuOpen ? '✕' : '☰' }}</span>
					</button>
				</div>
			</div>

			<nav
				:aria-label="__('Sections')"
				class="hidden flex-wrap items-center justify-between gap-x-7 gap-y-2 pb-4 pt-5 xl:flex"
			>
				<button
					v-for="menu in menus"
					:key="menu.id"
					type="button"
					class="lp-nav-link lp-nav-toggle"
					:aria-expanded="String(openPanel === menu.id)"
					:aria-controls="`lp-${menu.id}-menu`"
					@click="togglePanel(menu.id)"
				>
					{{ menu.label }}
					<svg
						width="14"
						height="14"
						viewBox="0 0 24 24"
						fill="none"
						stroke="currentColor"
						stroke-width="2.5"
						stroke-linecap="round"
						stroke-linejoin="round"
						aria-hidden="true"
						:class="{ 'rotate-180': openPanel === menu.id }"
					>
						<path d="M6 9l6 6 6-6" />
					</svg>
				</button>
				<a
					v-for="link in links"
					:key="link.label"
					:href="safeUrl(link.href)"
					class="lp-nav-link relative"
					>{{ link.label
					}}<span v-if="link.isNew" class="lp-new-tag">{{ __('NEW') }}</span></a
				>
			</nav>
		</div>

		<div v-if="menuOpen" id="lp-mobile-menu" class="lp-mobile-menu xl:hidden">
			<button
				v-for="menu in menus"
				:key="menu.id"
				type="button"
				class="lp-mobile-link text-left"
				:aria-expanded="String(openPanel === menu.id)"
				:aria-controls="`lp-${menu.id}-menu`"
				@click="openFromMobileMenu(menu.id)"
			>
				{{ menu.label }}
			</button>
			<a
				v-for="link in links"
				:key="link.label"
				:href="safeUrl(link.href)"
				class="lp-mobile-link"
				@click="menuOpen = false"
			>
				{{ link.label }}
			</a>
			<a href="/login" class="lp-btn-primary mt-3">{{ __('Register') }}</a>
			<a href="/login" class="lp-btn-outline mt-2">{{ __('Login') }}</a>
		</div>

		<div
			v-if="openPanel"
			:id="`lp-${openPanel}-menu`"
			class="lp-programmes-menu"
		>
			<div class="lp-container py-8">
				<div class="mb-6 flex flex-wrap items-center justify-between gap-3">
					<h2 class="lp-heading text-2xl">
						{{
							openPanel === 'classroom'
								? __('Courses offered by {0}').format(brand.name)
								: __('Online courses by {0}').format(brand.name)
						}}
					</h2>
					<button
						type="button"
						class="lp-icon-button"
						:aria-label="__('Close courses')"
						@click="openPanel = null"
					>
						<svg
							width="18"
							height="18"
							viewBox="0 0 24 24"
							fill="none"
							stroke="currentColor"
							stroke-width="2.5"
							stroke-linecap="round"
							aria-hidden="true"
						>
							<path d="M6 6l12 12M18 6L6 18" />
						</svg>
					</button>
				</div>

				<ul
					v-if="openPanel === 'classroom'"
					class="grid gap-4 [grid-template-columns:repeat(auto-fit,minmax(260px,1fr))]"
				>
					<li
						v-for="course in classroomCourses"
						:key="course.name"
						class="lp-course-item"
					>
						<span class="lp-heading text-lg">{{ __(course.name) }}</span>
						<span class="lp-class-detail">{{ __(course.classes) }}</span>
						<span class="text-sm leading-relaxed text-[var(--lp-caption)]">{{
							__(course.text)
						}}</span>
					</li>
				</ul>

				<template v-else>
					<p class="lp-app-note">
						<svg
							width="22"
							height="22"
							viewBox="0 0 24 24"
							fill="none"
							stroke="currentColor"
							stroke-width="2"
							stroke-linecap="round"
							stroke-linejoin="round"
							aria-hidden="true"
						>
							<rect x="6" y="2" width="12" height="20" rx="2.5" />
							<path d="M11 18h2" />
						</svg>
						<span>{{
							__('Live classes are taken on our {0} mobile app.').format(
								brand.name,
							)
						}}</span>
					</p>
					<p v-if="onlineCourses.loading" class="lp-muted">
						{{ __('Loading courses…') }}
					</p>
					<p v-else-if="!onlineList.length" class="lp-muted">
						{{ __('Online courses will be listed here soon.') }}
					</p>
					<ul
						v-else
						class="grid gap-4 [grid-template-columns:repeat(auto-fit,minmax(260px,1fr))]"
					>
						<li v-for="course in onlineList" :key="course.name">
							<a
								:href="safeUrl(`/lms/courses/${course.name}`)"
								class="lp-course-item lp-course-link"
							>
								<span class="lp-heading text-lg">{{ course.title }}</span>
								<span class="lp-class-detail">{{
									course.paid_course ? __('Paid · Online') : __('Free · Online')
								}}</span>
								<span
									v-if="course.short_introduction"
									class="text-sm leading-relaxed text-[var(--lp-caption)]"
									>{{ course.short_introduction }}</span
								>
							</a>
						</li>
					</ul>
				</template>
			</div>
		</div>
	</header>
</template>

<script setup lang="ts">
import { computed, ref } from 'vue'
import { createResource } from 'frappe-ui'
import { safeUrl } from '@/utils/safeUrl'
import { classroomCourses } from '@/pages/Landing/content'
import type { LandingContent } from '@/pages/Landing/content'

type Panel = 'classroom' | 'online'
interface OnlineCourse {
	name: string
	title: string
	short_introduction?: string | null
	paid_course: 0 | 1
	delivery: 'offline' | 'online'
}

const props = defineProps<{
	brand: { name: string; logo: string | null }
	branches: LandingContent['branches']
	contactPhone: string
}>()

const menuOpen = ref(false)
const openPanel = ref<Panel | null>(null)
const branchIndex = ref(0)

const menus: { id: Panel; label: string }[] = [
	{ id: 'classroom', label: __('Classroom Programmes') },
	{ id: 'online', label: __('Online Courses') },
]

// Fetched the first time the Online Courses menu opens, not on every page load.
const onlineCourses = createResource({
	url: 'lms.lms.api.get_landing_courses',
	params: { limit: 24 },
})
const onlineList = computed<OnlineCourse[]>(() =>
	((onlineCourses.data as OnlineCourse[]) || []).filter(
		(course) => course.delivery === 'online',
	),
)

const currentBranch = computed(
	() => props.branches[branchIndex.value % props.branches.length],
)
const branchName = computed(
	() => currentBranch.value?.label || currentBranch.value?.name || '',
)
// The call button rings the chosen branch, or the main number when it has none.
const phone = computed(() => currentBranch.value?.phone || props.contactPhone)

function nextBranch() {
	branchIndex.value = (branchIndex.value + 1) % props.branches.length
}

function togglePanel(panel: Panel) {
	openPanel.value = openPanel.value === panel ? null : panel
	if (
		openPanel.value === 'online' &&
		!onlineCourses.data &&
		!onlineCourses.loading
	) {
		onlineCourses.fetch()
	}
}

function openFromMobileMenu(panel: Panel) {
	menuOpen.value = false
	openPanel.value = null
	togglePanel(panel)
}

const links = [
	{ href: '#test-series', label: __('Test Series') },
	{ href: '#why', label: __('Study Material') },
	{ href: '#test-series', label: __('Scholarships'), isNew: true },
	{ href: '#branches', label: __('Branches') },
	{ href: '#contact', label: __('Contact') },
]
</script>
