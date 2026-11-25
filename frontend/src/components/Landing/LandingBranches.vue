<template>
	<section v-if="branches.length" id="branches" class="lp-section scroll-mt-24">
		<div class="lp-container">
			<h2 class="lp-section-title">{{ __('Our classroom centres') }}</h2>
			<div
				class="mt-8 grid gap-5 [grid-template-columns:repeat(auto-fit,minmax(260px,1fr))]"
			>
				<article
					v-for="branch in branches"
					:key="branch.label + branch.name"
					class="lp-card flex flex-col gap-2.5 p-6"
				>
					<p class="lp-eyebrow">{{ branch.label }}</p>
					<h3 v-if="branch.name" class="lp-heading text-[19px]">
						{{ branch.name }}
					</h3>
					<p
						v-if="branch.address"
						class="flex-1 text-sm leading-relaxed text-[var(--lp-caption)]"
					>
						{{ branch.address }}
					</p>
					<a
						v-if="branch.phone"
						:href="safeUrl(`tel:${branch.phone.replace(/[^\d+]/g, '')}`)"
						class="lp-link inline-flex min-h-[44px] items-center font-semibold"
						>{{ __('Phone') }}: {{ branch.phone }}</a
					>
				</article>
			</div>
		</div>
	</section>
</template>

<script setup lang="ts">
import { safeUrl } from '@/utils/safeUrl'
import type { LandingContent } from '@/pages/Landing/content'

defineProps<{ branches: LandingContent['branches'] }>()
</script>
