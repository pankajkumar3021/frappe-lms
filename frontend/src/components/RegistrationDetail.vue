<template>
	<Dialog v-model:open="open" :title="registration?.full_name" size="md">
		<template #default>
			<div v-if="registration" class="flex flex-col gap-4">
				<dl class="grid grid-cols-2 gap-3 text-p-base">
					<div>
						<dt class="text-ink-gray-6">{{ __('Contact number') }}</dt>
						<dd>
							<a
								:href="safeUrl(`tel:${registration.contact_number}`)"
								class="text-ink-blue-3 hover:underline"
							>
								{{ registration.contact_number }}
							</a>
						</dd>
					</div>
					<div>
						<dt class="text-ink-gray-6">{{ __('Class') }}</dt>
						<dd>{{ registration.student_class }}</dd>
					</div>
					<div>
						<dt class="text-ink-gray-6">{{ __('City') }}</dt>
						<dd>{{ registration.city }}</dd>
					</div>
					<div>
						<dt class="text-ink-gray-6">{{ __('Interested in') }}</dt>
						<dd>{{ interest }}</dd>
					</div>
				</dl>
				<FormControl
					v-model="form.follow_up_status"
					type="select"
					:label="__('Status')"
					:options="statusOptions"
				/>
				<FormControl
					v-model="form.assigned_to"
					type="select"
					:label="__('Assigned to')"
					:options="assigneeOptions"
				/>
				<FormControl
					v-model="form.follow_up_notes"
					type="textarea"
					:label="__('Notes')"
					:rows="4"
				/>
			</div>
		</template>
		<template #actions>
			<div class="pb-5 float-end">
				<Button variant="solid" :loading="saving" @click="save">
					{{ __('Save') }}
				</Button>
			</div>
		</template>
	</Dialog>
</template>

<script setup lang="ts">
import { Button, call, Dialog, FormControl, toast } from 'frappe-ui'
import { computed, reactive, ref, watch } from 'vue'
import { resourceErrorMessage } from '@/utils/resource'
import { safeUrl } from '@/utils/safeUrl'
import { FOLLOW_UP_STATUSES, type RegistrationRow } from '@/utils/registrations'

const props = defineProps<{
	registration: RegistrationRow | null
	team: { value: string; label: string }[]
}>()
const emit = defineEmits<{ saved: [] }>()
const open = defineModel<boolean>('open', { default: false })

const saving = ref(false)
const form = reactive({
	follow_up_status: 'New',
	assigned_to: '',
	follow_up_notes: '',
})

watch(
	() => [props.registration, open.value] as const,
	([row, isOpen]) => {
		if (!row || !isOpen) return
		form.follow_up_status = row.follow_up_status || 'New'
		form.assigned_to = row.assigned_to || ''
		form.follow_up_notes = row.follow_up_notes || ''
	},
	{ immediate: true }
)

const statusOptions = computed(() =>
	FOLLOW_UP_STATUSES.map((status) => ({ label: __(status), value: status }))
)

// A current assignee who has since left the team stays visible, so saving the
// dialog does not silently clear them.
const assigneeOptions = computed(() => {
	const options = [{ label: __('Unassigned'), value: '' }, ...props.team]
	const current = props.registration?.assigned_to
	if (current && !options.some((option) => option.value === current)) {
		options.push({
			label: props.registration?.assigned_to_name || current,
			value: current,
		})
	}
	return options
})

const interest = computed(() => {
	const parts = []
	if (props.registration?.wants_online) parts.push(__('Online'))
	if (props.registration?.wants_classroom) parts.push(__('Classroom'))
	return parts.join(', ')
})

async function save() {
	if (!props.registration || saving.value) return
	saving.value = true
	try {
		await call('lms.lms.registration.update_registration', {
			name: props.registration.name,
			follow_up_status: form.follow_up_status,
			assigned_to: form.assigned_to,
			follow_up_notes: form.follow_up_notes,
		})
		toast.success(__('Registration updated'))
		open.value = false
		emit('saved')
	} catch (error: unknown) {
		toast.error(
			resourceErrorMessage(error, __('Could not save the registration'))
		)
	} finally {
		saving.value = false
	}
}
</script>
