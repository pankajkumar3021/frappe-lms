<template>
	<div
		class="mx-auto flex min-h-screen w-full max-w-md flex-col justify-center p-6"
	>
		<div
			v-if="loadFailed"
			class="flex flex-col items-center gap-4 text-center"
			role="alert"
		>
			<p class="text-p-base text-ink-gray-7">
				{{
					__('Could not load the form. Check your connection and try again.')
				}}
			</p>
			<Button variant="solid" :label="__('Try again')" @click="load" />
		</div>

		<form
			v-else-if="loaded"
			class="flex flex-col gap-5"
			novalidate
			@submit.prevent="submit"
		>
			<div>
				<h1 class="text-2xl-semibold text-ink-gray-9">
					{{ __('Tell us about yourself') }}
				</h1>
				<p class="mt-1.5 text-p-base text-ink-gray-6">
					{{ __('This takes a minute and we ask it only once.') }}
				</p>
			</div>

			<FormControl
				v-model="form.full_name"
				type="text"
				:label="__('Full name')"
				autocomplete="name"
				:required="true"
				:error="touched.full_name ? nameError : undefined"
				@blur="touched.full_name = true"
			/>

			<FormControl
				v-model="form.contact_number"
				type="text"
				inputmode="tel"
				autocomplete="tel-national"
				:label="__('Contact number')"
				:required="true"
				:error="touched.contact_number ? numberError : undefined"
				@blur="touched.contact_number = true"
			>
				<template #prefix>
					<span class="text-p-base text-ink-gray-6">+91</span>
				</template>
			</FormControl>

			<FormControl
				v-model="form.student_class"
				type="select"
				:label="__('Class')"
				:required="true"
				:options="classOptions"
			/>

			<FormControl
				v-model="form.city"
				type="select"
				:label="__('City')"
				:required="true"
				:options="cityOptions"
			/>

			<fieldset class="flex flex-col gap-2">
				<legend class="mb-1 text-p-sm text-ink-gray-6">
					{{ __("I'm interested in") }}
				</legend>
				<FormControl
					v-model="form.wants_online"
					type="checkbox"
					:label="__('Online courses')"
				/>
				<FormControl
					v-model="form.wants_classroom"
					type="checkbox"
					:label="__('Classroom courses')"
				/>
			</fieldset>

			<p v-if="serverError" class="text-p-sm text-ink-red-4" role="alert">
				{{ serverError }}
			</p>

			<Button
				type="submit"
				variant="solid"
				size="md"
				:label="__('Continue')"
				:disabled="!canSubmit"
				:loading="submitting"
			/>
		</form>
	</div>
</template>

<script setup lang="ts">
import { Button, FormControl, call, usePageMeta } from 'frappe-ui'
import { computed, onMounted, reactive, ref } from 'vue'
import { useRouter } from 'vue-router'
import { usersStore } from '@/stores/user'
import { resourceErrorMessage } from '@/utils/resource'
import { useRegistrationState } from '@/composables/useRegistrationState'

const router = useRouter()
const { userResource } = usersStore()
const { getState, markRegistered } = useRegistrationState()

const loaded = ref(false)
const loadFailed = ref(false)
const submitting = ref(false)
const serverError = ref('')
const classes = ref<string[]>([])
const cities = ref<string[]>([])

const form = reactive({
	full_name: '',
	contact_number: '',
	student_class: '',
	city: '',
	wants_online: false,
	wants_classroom: false,
})
const touched = reactive({ full_name: false, contact_number: false })

const toOptions = (values: string[]) =>
	values.map((value) => ({ label: value, value }))
const classOptions = computed(() => toOptions(classes.value))
const cityOptions = computed(() => toOptions(cities.value))

// The server cleans the number up; the client only counts digits once spaces
// and a +91 prefix are gone.
const digits = computed(() =>
	form.contact_number.replace(/[\s-]/g, '').replace(/^\+?91(?=\d{10}$)/, ''),
)
const numberValid = computed(() => /^\d{10}$/.test(digits.value))
const nameError = computed(() =>
	form.full_name.trim() ? undefined : __('Enter your full name'),
)
const numberError = computed(() =>
	numberValid.value ? undefined : __('Enter a 10-digit mobile number'),
)

const canSubmit = computed(
	() =>
		!submitting.value &&
		Boolean(form.full_name.trim()) &&
		numberValid.value &&
		Boolean(form.student_class) &&
		Boolean(form.city) &&
		(form.wants_online || form.wants_classroom),
)

async function load() {
	loadFailed.value = false
	try {
		const state = await getState()
		if (!state.needs_registration) {
			router.replace({ name: 'Courses' })
			return
		}
		classes.value = state.classes
		cities.value = state.cities
		form.full_name = state.prefill?.full_name || ''
		form.contact_number = state.prefill?.contact_number || ''
		loaded.value = true
	} catch (_) {
		loadFailed.value = true
	}
}

async function submit() {
	if (!canSubmit.value) return
	submitting.value = true
	serverError.value = ''
	try {
		const result = await call('lms.lms.registration.submit_registration', {
			full_name: form.full_name.trim(),
			contact_number: form.contact_number,
			student_class: form.student_class,
			city: form.city,
			wants_online: form.wants_online ? 1 : 0,
			wants_classroom: form.wants_classroom ? 1 : 0,
		})
		markRegistered()
		userResource.reload()
		router.replace({
			name: 'Courses',
			query: { class: result?.student_class || form.student_class },
		})
	} catch (error: unknown) {
		serverError.value = resourceErrorMessage(
			error,
			__('Could not save your details. Please try again.'),
		)
	} finally {
		submitting.value = false
	}
}

onMounted(load)

usePageMeta(() => ({ title: __('Tell us about yourself') }))
</script>
