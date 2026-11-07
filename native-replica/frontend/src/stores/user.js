import { defineStore } from 'pinia'
import { api, getToken, AUTH_EXPIRED_EVENT, getDeviceInfo } from '../api'
import { isMock } from '../bridge'

const ECARD_KEY = 'ets_ecard_id'
const PROFILE_KEY = 'ets_profile'
let bootstrapPromise = null

function readJSON(key, fallback) {
  try {
    const raw = localStorage.getItem(key)
    return raw ? JSON.parse(raw) : fallback
  } catch { return fallback }
}

export const useUserStore = defineStore('user', {
  state: () => ({
    token: getToken(),
    profile: readJSON(PROFILE_KEY, null),
    ecards: [],
    activeEcardId: (() => { try { return localStorage.getItem(ECARD_KEY) || '' } catch { return '' } })(),
    systemConfig: {},
    announcement: null,
    device: null,
    loading: false,
    ready: false,
    lastError: ''
  }),

  getters: {
    isLoggedIn: (state) => !!state.token,
    displayName: (state) => (state.profile && (state.profile.name || state.profile.phone)) || '同学',
    gradeName: (state) => {
      const ecard = state.ecards.find((e) => String(e.id) === String(state.activeEcardId))
      return (ecard && ecard.grade) || (state.profile && state.profile.grade_name) || ''
    },
    activeEcard: (state) => state.ecards.find((e) => String(e.id) === String(state.activeEcardId)) || state.ecards[0] || null,
    schoolName: (state) => {
      const ecard = state.ecards.find((e) => String(e.id) === String(state.activeEcardId))
      return (ecard && ecard.school_name) || ''
    },
    isMockMode: () => isMock
  },

  actions: {
    async login(phone, password) {
      const body = await api.login(phone, password)
      this.token = getToken()
      this.profile = {
        ...(this.profile || {}),
        name: body.name,
        phone: body.phone,
        raw_phone: body.raw_phone,
        recent_account_id: body.recent_account_id
      }
      this.ready = false
      await this.bootstrap(true)
      return body
    },

    async bootstrap(force = false) {
      if (this.ready && !force) return
      if (!this.token) return
      if (bootstrapPromise && !force) return bootstrapPromise
      bootstrapPromise = this._bootstrap()
      try {
        return await bootstrapPromise
      } finally {
        bootstrapPromise = null
      }
    },

    async _bootstrap() {
      this.loading = true
      this.lastError = ''
      try {
        const results = await Promise.allSettled([
          api.getUserInfo(),
          api.getEcardList(),
          api.getSystemConfig(),
          api.getAnnouncements(),
          getDeviceInfo()
        ])
        const [profileRes, ecardRes, configRes, announceRes, deviceRes] = results

        if (profileRes.status === 'fulfilled' && profileRes.value) {
          this.profile = { ...(this.profile || {}), ...profileRes.value }
          try { localStorage.setItem(PROFILE_KEY, JSON.stringify(this.profile)) } catch { /* ignore */ }
        }
        if (ecardRes.status === 'fulfilled' && ecardRes.value) {
          this.ecards = ecardRes.value.data || []
          const stillValid = this.ecards.some((e) => String(e.id) === String(this.activeEcardId))
          if (!stillValid) {
            const preferred = this.ecards.find((e) => this.profile && String(e.grade_id) === String(this.profile.grade_id))
            this.setActiveEcard((preferred || this.ecards[0] || {}).id || '')
          }
        }
        if (configRes.status === 'fulfilled' && configRes.value) this.systemConfig = configRes.value || {}
        if (announceRes.status === 'fulfilled' && announceRes.value) this.announcement = announceRes.value
        if (deviceRes.status === 'fulfilled' && deviceRes.value) this.device = deviceRes.value

        const rejected = results.find((r) => r.status === 'rejected')
        if (rejected) this.lastError = rejected.reason && rejected.reason.message ? rejected.reason.message : String(rejected.reason)
      } catch (e) {
        // Never leave the UI stuck on the loading panel: a synchronous throw in any
        // request helper must still mark bootstrap as finished.
        this.lastError = e && e.message ? e.message : String(e)
      } finally {
        this.loading = false
        this.ready = true
      }
    },

    setActiveEcard(id) {
      this.activeEcardId = String(id || '')
      try { localStorage.setItem(ECARD_KEY, this.activeEcardId) } catch { /* ignore */ }
      const card = this.ecards.find((e) => String(e.id) === String(this.activeEcardId))
      if (card && card.parent_id) {
        try { localStorage.setItem('ets_parent_account_id', String(card.parent_id)) } catch { /* ignore */ }
      }
    },

    reset() {
      this.token = ''
      this.profile = null
      this.ecards = []
      this.activeEcardId = ''
      this.systemConfig = {}
      this.announcement = null
      this.ready = false
      this.loading = false
      try {
        localStorage.removeItem(PROFILE_KEY)
        localStorage.removeItem(ECARD_KEY)
      } catch { /* ignore */ }
    },

    async logout() {
      await api.logout()
      this.reset()
    }
  }
})

export { AUTH_EXPIRED_EVENT }
