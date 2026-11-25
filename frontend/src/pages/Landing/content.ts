// Landing page copy that is not stored in LMS Settings. Brand elements (name,
// logo, colour, promo, hero, branches and contact) come from LMS Settings
// through lms.lms.api.get_landing_content. Programmes, the course list, the
// reasons to join and the test series below are written here. Each string is
// passed through __() where it is shown.

export interface LandingContent {
	enabled: boolean
	brand: { name: string; logo: string | null; primary_colour: string }
	promo: string
	hero: { eyebrow: string; headline: string; lede: string }
	slides: {
		eyebrow: string
		title: string
		text: string
		cta: { label: string; href: string }
	}[]
	branches: { label: string; name: string; address: string; phone: string }[]
	contact: { phone: string; email: string; website: string }
}

// Shown when the hero fields in LMS Settings are blank.
export const heroDefaults = {
	eyebrow: 'Building your foundation',
	headline: 'for a brighter future',
	lede: 'Classroom coaching for Class 5 to 12, CBSE and Bihar Board, taught by IIT, NIT and Kota alumni with the 5-E learning method.',
}

// Stroke icons, drawn on a 24 by 24 grid.
const icons = {
	cap: 'M12 3l9 5-9 5-9-5 9-5zM5 10.5V16c0 1.5 3 3 7 3s7-1.5 7-3v-5.5',
	paper: 'M4 4h12l4 4v12H4zM8 12h8M8 16h5',
	rocket:
		'M12 2c3 2 5 6 5 10l-2 4H9l-2-4c0-4 2-8 5-10zM9 16l-3 4M15 16l3 4M12 9.5v.01',
	chart: 'M4 20V10M10 20V4M16 20v-7M22 20H2',
	clock: 'M12 3a9 9 0 1 0 0 18 9 9 0 0 0 0-18zM12 7v5l3 2',
	people:
		'M16 21v-2a4 4 0 0 0-4-4H6a4 4 0 0 0-4 4v2M9 11a4 4 0 1 0 0-8 4 4 0 0 0 0 8zM22 21v-2a4 4 0 0 0-3-3.9M16 3.1a4 4 0 0 1 0 7.8',
	book: 'M4 19.5A2.5 2.5 0 0 1 6.5 17H20V3H6.5A2.5 2.5 0 0 0 4 5.5zM20 17v4H6.5',
	check:
		'M9 11l3 3 8-8M20 12v7a2 2 0 0 1-2 2H6a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h9',
}

export interface Programme {
	name: string
	classes: string
	icon: string
	tone: 'purple' | 'indigo' | 'green' | 'sky'
}

// The four cards under the hero.
export const programmes: Programme[] = [
	{
		name: 'Foundation',
		classes: 'Class 5–8 · Olympiad',
		icon: icons.cap,
		tone: 'purple',
	},
	{
		name: 'Pre-Board',
		classes: 'Class 9–10 · Boards',
		icon: icons.paper,
		tone: 'indigo',
	},
	{
		name: 'Launch Pad',
		classes: 'Class 11–12 · JEE / NEET',
		icon: icons.rocket,
		tone: 'green',
	},
	{
		name: 'IIT-JEE / NEET Rank Booster',
		classes: 'Class 12 pass-outs',
		icon: icons.chart,
		tone: 'sky',
	},
]

// The list that opens from "Classroom Programmes" in the header.
export const classroomCourses: {
	name: string
	classes: string
	text: string
}[] = [
	{
		name: 'Foundation',
		classes: 'Class 5–8',
		text: 'Concept clarity, problem solving and reasoning, with Navodaya and AIIMS school entrance readiness.',
	},
	{
		name: 'Pre-Board',
		classes: 'Class 9–10',
		text: 'Board exam focus with a competitive foundation and weekly tests.',
	},
	{
		name: 'Launch Pad',
		classes: 'Class 11–12 Science (PCM / PCB)',
		text: 'Bridge course covering the JEE and NEET syllabus alongside the boards.',
	},
	{
		name: 'IIT-JEE / NEET Rank Booster',
		classes: 'Class 12 pass-outs',
		text: 'One-year intensive programme for the entrance exams.',
	},
	{
		name: 'G.R.E.A.T. Test Series',
		classes: 'Class 10 and 12',
		text: '20 tests with cash prizes for the top three and a 50% fee waiver above 80%.',
	},
	{
		name: 'Marks Booster Crash Course',
		classes: 'Board students',
		text: 'Eight-week crash course before the board exams.',
	},
	{
		name: 'Olympiad Batch',
		classes: 'Foundation students',
		text: 'Extra practice for the science and maths Olympiads.',
	},
	{
		name: 'Fluent English',
		classes: 'All classes',
		text: 'Spoken and written English proficiency programme.',
	},
	{
		name: 'Navodaya Preparation',
		classes: 'Entrance aspirants',
		text: 'Focused preparation for the Navodaya Vidyalaya entrance test.',
	},
]

// "Why Gradex?", beside the hero photo.
export const whyUs: { title: string; text: string; icon: string }[] = [
	{
		title: '5-E learning method',
		text: 'Engage, Explore, Explain, Elaborate, Evaluate: every chapter moves through all five steps.',
		icon: icons.clock,
	},
	{
		title: 'Faculty from IIT, NIT, Kota',
		text: 'Teachers who have sat the same exams your child is preparing for.',
		icon: icons.people,
	},
	{
		title: 'Material built for recall',
		text: 'Notes use dual coding and active recall, so revision sticks before the board exam.',
		icon: icons.book,
	},
	{
		title: 'Weekly tests',
		text: 'A test every week shows where each student stands, long before the final exam.',
		icon: icons.check,
	},
]

// The hero's fact strip. The branch count is added from LMS Settings.
export const heroFacts: { value: string; label: string }[] = [
	{ value: 'Class 5–12', label: 'Foundation to JEE / NEET' },
	{ value: 'Up to 50%', label: 'Scholarship on fees' },
]

export const testSeries = {
	label: 'For Class 10 and 12',
	headline: 'G.R.E.A.T. Test Series',
	text: '20 tests across the year. Score above 80% and get a 50% fee waiver. The free scholarship test runs every weekend.',
	prizes: [
		{ place: '1st prize', amount: '₹50,000' },
		{ place: '2nd prize', amount: '₹30,000' },
		{ place: '3rd prize', amount: '₹20,000' },
	],
}
