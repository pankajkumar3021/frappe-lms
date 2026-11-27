export const FOLLOW_UP_STATUSES = [
	'New',
	'Contacted',
	'Joined',
	'Not interested',
] as const

export interface RegistrationRow {
	name: string
	full_name: string
	contact_number: string
	student_class: string
	city: string
	wants_online: number
	wants_classroom: number
	follow_up_status: string
	assigned_to: string | null
	assigned_to_name: string
	follow_up_notes: string | null
	registered_on: string
}
