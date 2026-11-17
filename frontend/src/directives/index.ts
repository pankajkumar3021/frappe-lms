import type { App } from 'vue'
import safeHtml from './safeHtml'
import mathText from './mathText'
import { vExternal } from './external'

export { safeHtml, mathText, vExternal }

export function registerDirectives(app: App) {
	app.directive('safe-html', safeHtml)
	app.directive('math-text', mathText)
	app.directive('external', vExternal)
}
