<template>
	<ListPage
		:breadcrumbs="breadcrumbs"
		:title="__('Registrations')"
		layout="list"
		:columns="columns"
		:rows="rows"
		:loading="loading"
		:total-count="count"
		:has-next-page="rows.length < count"
		:list-options="listOptions"
		v-model:page-length="pageLength"
		:filtered="isFiltered"
		empty-name="Registrations"
		empty-icon="lucide-phone-call"
		:empty-title="__('No registrations yet')"
		:empty-description="__('Students who register show up here for follow-up.')"
		@load-more="loadMore"
		@clear-filters="clearFilters"
	>
		<template #filters>
			<ClearableCombobox
				v-model="filters.follow_up_status"
				:options="statusOptions"
				:placeholder="__('Status')"
				:ariaLabel="__('Status')"
			/>
			<ClearableCombobox
				v-if="classOptions.length"
				v-model="filters.student_class"
				:options="classOptions"
				:placeholder="__('Class')"
				:ariaLabel="__('Class')"
			/>
			<ClearableCombobox
				v-if="cityOptions.length"
				v-model="filters.city"
				:options="cityOptions"
				:placeholder="__('City')"
				:ariaLabel="__('City')"
			/>
			<ToggleFilter
				v-model="filters.classroomOnly"
				:label="__('Classroom only')"
			/>
			<ToggleFilter
				v-model="filters.assignedToMe"
				:label="__('Assigned to me')"
			/>
		</template>

		<template #cell="{ column, row, value }">
			<a
				v-if="column.key === 'contact_number'"
				:href="safeUrl(`tel:${value}`)"
				class="text-ink-blue-3 hover:underline"
				@click.stop
			>
				{{ value }}
			</a>
			<span v-else-if="column.key === 'interest'">{{ interestOf(row) }}</span>
			<span
				v-else-if="column.key === 'registered_on'"
				class="text-sm text-ink-gray-6"
			>
				{{ formatDate(value) }}
			</span>
			<span v-else-if="column.key === 'follow_up_status'">
				{{ __(String(value)) }}
			</span>
			<div v-else class="truncate">{{ value }}</div>
		</template>
	</ListPage>

	<RegistrationDetail
		v-model:open="detailOpen"
		:registration="selected"
		:team="team"
		@saved="reload"
	/>
</template>

<script setup lang="ts">
import { call, usePageMeta } from 'frappe-ui'
import { computed, inject, onMounted, reactive, ref, watch } from 'vue'
import ClearableCombobox from '@/components/Controls/ClearableCombobox.vue'
import ToggleFilter from '@/components/Controls/ToggleFilter.vue'
import ListPage from '@/components/Layouts/pages/ListPage.vue'
import RegistrationDetail from '@/components/RegistrationDetail.vue'
import { sessionStore } from '@/stores/session'
import { useRegistrationState } from '@/composables/useRegistrationState'
import { FOLLOW_UP_STATUSES, type RegistrationRow } from '@/utils/registrations'
import { resourceErrorMessage } from '@/utils/resource'
import { safeUrl } from '@/utils/safeUrl'
import { toast } from 'frappe-ui'
import type {
	Breadcrumb,
	ListColumn,
	ListRow,
	ListViewOptions,
	SessionUser,
} from '@/types'

const { brand } = sessionStore()
const user = inject('$user') as SessionUser
const dayjs = inject('$dayjs') as (date: string) => {
	format: (fmt: string) => string
}

const filters = reactive<{
	follow_up_status: string | null
	student_class: string | null
	city: string | null
	classroomOnly: boolean
	assignedToMe: boolean
}>({
	follow_up_status: 'New',
	student_class: null,
	city: null,
	classroomOnly: true,
	assignedToMe: false,
})

const rows = ref<RegistrationRow[]>([])
const count = ref(0)
const loading = ref(false)
const pageLength = ref(24)
const classNames = ref<string[]>([])
const cityNames = ref<string[]>([])
const team = ref<{ value: string; label: string }[]>([])
const selected = ref<RegistrationRow | null>(null)
const detailOpen = ref(false)

function activeFilters(): Record<string, string | number> {
	const active: Record<string, string | number> = {}
	if (filters.follow_up_status)
		active.follow_up_status = filters.follow_up_status
	if (filters.classroomOnly) active.wants_classroom = 1
	if (filters.student_class) active.student_class = filters.student_class
	if (filters.city) active.city = filters.city
	if (filters.assignedToMe && user.data?.name)
		active.assigned_to = user.data.name
	return active
}

// A slower, older response must not overwrite a newer one.
let requestId = 0

async function load(append = false) {
	const id = ++requestId
	loading.value = true
	try {
		const result = await call('lms.lms.registration.get_registrations', {
			filters: activeFilters(),
			start: append ? rows.value.length : 0,
			page_length: pageLength.value,
		})
		if (id !== requestId) return
		rows.value = append ? [...rows.value, ...result.rows] : result.rows
		count.value = result.count
	} catch (error: unknown) {
		if (id !== requestId) return
		toast.error(resourceErrorMessage(error, __('Could not load registrations')))
	} finally {
		if (id === requestId) loading.value = false
	}
}

const reload = () => load()
const loadMore = () => load(true)

watch([filters, pageLength], reload, { deep: true })

onMounted(async () => {
	load()
	call('lms.lms.registration.get_registration_team')
		.then(
			(members: { value: string; label: string }[]) => (team.value = members)
		)
		.catch(() => {})
	try {
		const state = await useRegistrationState().getState()
		classNames.value = state.classes || []
		cityNames.value = state.cities || []
	} catch (_) {
		// The class and city filters stay hidden; the list still works.
	}
})

const isFiltered = computed(
	() =>
		Boolean(filters.follow_up_status) ||
		filters.classroomOnly ||
		Boolean(filters.student_class) ||
		Boolean(filters.city) ||
		filters.assignedToMe
)

function clearFilters() {
	filters.follow_up_status = null
	filters.student_class = null
	filters.city = null
	filters.classroomOnly = false
	filters.assignedToMe = false
}

const statusOptions = computed(() =>
	FOLLOW_UP_STATUSES.map((status) => ({ label: __(status), value: status }))
)
const classOptions = computed(() =>
	classNames.value.map((name) => ({ label: name, value: name }))
)
const cityOptions = computed(() =>
	cityNames.value.map((name) => ({ label: name, value: name }))
)

const interestOf = (row: ListRow) =>
	[
		row.wants_online ? __('Online') : '',
		row.wants_classroom ? __('Classroom') : '',
	]
		.filter(Boolean)
		.join(', ')

const formatDate = (value: unknown) =>
	value ? dayjs(String(value)).format('DD MMM YYYY') : ''

const listOptions: ListViewOptions = {
	selectable: false,
	showTooltip: false,
	onRowClick: (row: ListRow) => {
		selected.value = row as unknown as RegistrationRow
		detailOpen.value = true
	},
}

const columns = computed<ListColumn[]>(() => [
	{ label: __('Name'), key: 'full_name', width: 2, icon: 'lucide-user' },
	{
		label: __('Class'),
		key: 'student_class',
		width: 1.25,
		icon: 'lucide-graduation-cap',
	},
	{ label: __('City'), key: 'city', width: 1, icon: 'lucide-map-pin' },
	{
		label: __('Interested in'),
		key: 'interest',
		width: 1.25,
		icon: 'lucide-monitor',
	},
	{
		label: __('Contact number'),
		key: 'contact_number',
		width: 1.5,
		icon: 'lucide-phone',
	},
	{
		label: __('Registered on'),
		key: 'registered_on',
		width: 1.25,
		icon: 'lucide-clock',
	},
	{
		label: __('Status'),
		key: 'follow_up_status',
		width: 1,
		icon: 'lucide-flag',
	},
	{
		label: __('Assigned to'),
		key: 'assigned_to_name',
		width: 1.5,
		icon: 'lucide-user-check',
	},
])

const breadcrumbs = computed<Breadcrumb[]>(() => [
	{ label: __('Registrations') },
])

usePageMeta(() => ({
	title: __('Registrations'),
	icon: brand.favicon,
}))
</script>
