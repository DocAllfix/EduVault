/**
 * UserAuthForm tests — Nexus EduVault.
 *
 * Original template tests mocked a Zustand `useAuthStore` with English
 * messages. After FASE 6.5 (api.ts) + 6.6 (this form), the auth flow goes
 * through `api.login()` which itself handles localStorage; the form no
 * longer touches the store. Copy is Italian. Forgot-password link and
 * social buttons are removed (REI-4).
 *
 * Tests here pin the new contract:
 *   - validation messages are Italian
 *   - on success → toast + navigate to "/" (or redirectTo)
 *   - on 401 → error toast + no navigate
 */

import { beforeEach, describe, expect, it, vi } from 'vitest'
import { render, type RenderResult } from 'vitest-browser-react'
import { type Locator, userEvent } from 'vitest/browser'
import { UserAuthForm } from './user-auth-form'

const FORM_MESSAGES = {
  emailEmpty: 'Inserisci la tua email.',
  passwordEmpty: 'Inserisci la password.',
} as const

const navigate = vi.fn()
const loginMock = vi.fn()
const toastSuccess = vi.fn()
const toastError = vi.fn()

vi.mock('@tanstack/react-router', async (importOriginal) => {
  const actual =
    await importOriginal<typeof import('@tanstack/react-router')>()
  return {
    ...actual,
    useNavigate: () => navigate,
  }
})

vi.mock('@/lib/api', async () => {
  // Re-implement ApiError locally to keep the assertion in this file
  // independent of api.ts internals.
  class ApiError extends Error {
    status: number
    constructor(status: number, message: string) {
      super(message)
      this.name = 'ApiError'
      this.status = status
    }
  }
  return {
    ApiError,
    api: { login: (...args: unknown[]) => loginMock(...args) },
  }
})

vi.mock('sonner', () => ({
  toast: {
    success: (...args: unknown[]) => toastSuccess(...args),
    error: (...args: unknown[]) => toastError(...args),
  },
}))

describe('UserAuthForm', () => {
  describe('Rendering', () => {
    let screen: RenderResult
    let emailInput: Locator
    let passwordInput: Locator
    let submitButton: Locator

    beforeEach(async () => {
      vi.clearAllMocks()
      screen = await render(<UserAuthForm />)
      emailInput = screen.getByRole('textbox', { name: /^Email$/i })
      passwordInput = screen.getByLabelText(/^Password$/i)
      submitButton = screen.getByRole('button', { name: /^Accedi$/i })
    })

    it('renders email, password, and submit button (no social, no forgot password)', async () => {
      await expect.element(emailInput).toBeInTheDocument()
      await expect.element(passwordInput).toBeInTheDocument()
      await expect.element(submitButton).toBeInTheDocument()
      // Social buttons removed (REI-4).
      expect(screen.container.textContent).not.toMatch(/GitHub|Facebook/i)
      // Forgot password removed (BP §08 v1.0: no self-service reset).
      expect(screen.container.textContent).not.toMatch(/Forgot|password dimenticata/i)
    })

    it('shows Italian validation messages on empty submit', async () => {
      await userEvent.click(submitButton)

      await expect
        .element(screen.getByText(FORM_MESSAGES.emailEmpty))
        .toBeInTheDocument()
      await expect
        .element(screen.getByText(FORM_MESSAGES.passwordEmpty))
        .toBeInTheDocument()

      expect(loginMock).not.toHaveBeenCalled()
    })

    it('calls api.login and navigates to "/" on success', async () => {
      loginMock.mockResolvedValueOnce({
        access_token: 'a',
        refresh_token: 'r',
        token_type: 'bearer',
      })

      await userEvent.fill(emailInput, 'a@b.com')
      await userEvent.fill(passwordInput, 'pw')
      await userEvent.click(submitButton)

      await vi.waitFor(() => expect(loginMock).toHaveBeenCalledOnce())
      expect(loginMock).toHaveBeenCalledWith('a@b.com', 'pw')

      await vi.waitFor(() =>
        expect(navigate).toHaveBeenCalledWith({ to: '/dashboard', replace: true })
      )
      expect(toastSuccess).toHaveBeenCalled()
      expect(toastError).not.toHaveBeenCalled()
    })

    it('shows error toast and does NOT navigate on 401', async () => {
      const { ApiError } = await import('@/lib/api')
      loginMock.mockRejectedValueOnce(
        new ApiError(401, 'Credenziali non valide')
      )

      await userEvent.fill(emailInput, 'a@b.com')
      await userEvent.fill(passwordInput, 'wrong')
      await userEvent.click(submitButton)

      await vi.waitFor(() => expect(toastError).toHaveBeenCalled())
      expect(toastError).toHaveBeenCalledWith('Credenziali non valide')
      expect(navigate).not.toHaveBeenCalled()
    })
  })

  it('navigates to redirectTo when provided', async () => {
    vi.clearAllMocks()
    loginMock.mockResolvedValueOnce({
      access_token: 'a',
      refresh_token: 'r',
      token_type: 'bearer',
    })

    const { getByRole, getByLabelText } = await render(
      <UserAuthForm redirectTo='/settings' />
    )

    await userEvent.fill(getByRole('textbox', { name: /Email/i }), 'a@b.com')
    await userEvent.fill(getByLabelText('Password'), 'pw')
    await userEvent.click(getByRole('button', { name: /Accedi/i }))

    await vi.waitFor(() =>
      expect(navigate).toHaveBeenCalledWith({
        to: '/settings',
        replace: true,
      })
    )
  })
})
