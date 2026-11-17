import { call, toast } from 'frappe-ui'
import type { FrappeResourceError } from 'frappe-ui'
import { useRouter } from 'vue-router'
import { resourceErrorMessage } from '@/utils/resource'
import type { CourseDetails, SessionUser } from '@/types'
import { isInstructorOf } from '@/utils/instructors'

// The query flag a guest carries through login (password or Google) so the
// course page finishes the enrollment they started, instead of making them
// press Enroll again.
export const ENROLL_AFTER_LOGIN = 'enroll'

export function loginToEnrollUrl(path: string): string {
	const target = `${path}?${ENROLL_AFTER_LOGIN}=1`
	return `/login?redirect-to=${encodeURIComponent(target)}`
}

// Whether the learner can enroll themselves with one click: a free course that
// allows self-learning and they are not yet in. Moderators and instructors see
// no Enroll button, so they are left out too.
export function canSelfEnroll(
	course: CourseDetails | null | undefined,
	user: SessionUser['data']
): boolean {
	if (!course || !user) return false
	if (course.membership || course.paid_course || course.disable_self_learning)
		return false
	if (user.is_moderator || isInstructorOf(course.instructors, user.username))
		return false
	return true
}

export function useCourseEnrollment(user: SessionUser) {
	const router = useRouter()

	function enroll(courseName: string): Promise<void> {
		if (!user.data) {
			toast.warning(__('You need to login first to enroll for this course'))
			setTimeout(() => {
				window.location.href = loginToEnrollUrl(window.location.pathname)
			}, 500)
			return Promise.resolve()
		}
		return call('frappe.client.insert', {
			doc: {
				doctype: 'LMS Enrollment',
				course: courseName,
				member: user.data.name,
			},
		})
			.then(() => {
				toast.success(__('You have been enrolled in this course'))
				setTimeout(() => {
					router.push({
						name: 'Lesson',
						params: { courseName, chapterNumber: 1, lessonNumber: 1 },
					})
				}, 1000)
			})
			.catch((err: FrappeResourceError) => {
				const msg = resourceErrorMessage(err, 'Error')
				toast.warning(__(msg))
				console.error(err)
			})
	}

	return { enroll }
}
