import { expect, test } from '@playwright/test'

const PAGE_PATH = '/kanto-first-person/'

test.describe('mobile field terminal', () => {
  test.use({ viewport: { width: 390, height: 844 } })

  test('is readable, touch-friendly, stacked, and scrollable', async ({ page }) => {
    await page.goto(PAGE_PATH)

    const layout = await page.evaluate(() => {
      const box = (rect: DOMRect) => ({
        bottom: rect.bottom,
        height: rect.height,
        left: rect.left,
        right: rect.right,
        top: rect.top,
        width: rect.width,
      })
      const root = document.querySelector<HTMLElement>('#root')!
      const menu = document.querySelector<HTMLElement>('.menu-window')!
      const detail = document.querySelector<HTMLElement>('.detail-window')!
      const heading = document.querySelector<HTMLElement>('.detail-copy h2')!
      const summary = document.querySelector<HTMLElement>('.detail-summary')!
      const canvas = document.querySelector<HTMLElement>('.world-canvas')!
      const menuButtons = [...document.querySelectorAll<HTMLElement>('.menu-window > button')]
      const interactive = [...document.querySelectorAll<HTMLElement>('button, a[href]')]

      return {
        root: {
          clientHeight: root.clientHeight,
          clientWidth: root.clientWidth,
          overflowX: getComputedStyle(root).overflowX,
          overflowY: getComputedStyle(root).overflowY,
          scrollHeight: root.scrollHeight,
          scrollWidth: root.scrollWidth,
        },
        menu: box(menu.getBoundingClientRect()),
        detail: box(detail.getBoundingClientRect()),
        heading: box(heading.getBoundingClientRect()),
        summary: {
          ...box(summary.getBoundingClientRect()),
          fontSize: Number.parseFloat(getComputedStyle(summary).fontSize),
        },
        canvas: {
          ...box(canvas.getBoundingClientRect()),
          position: getComputedStyle(canvas).position,
        },
        menuButtons: menuButtons.map((element) => ({
          ...box(element.getBoundingClientRect()),
          fontSize: Number.parseFloat(getComputedStyle(element).fontSize),
          touchAction: getComputedStyle(element).touchAction,
        })),
        interactive: interactive.map((element) => ({
          ...box(element.getBoundingClientRect()),
          text: element.textContent?.trim() ?? '',
        })),
      }
    })

    expect(layout.root.overflowX).toBe('hidden')
    expect(layout.root.overflowY).toBe('auto')
    expect(layout.root.scrollHeight).toBeGreaterThan(layout.root.clientHeight)
    expect(layout.root.scrollWidth).toBeLessThanOrEqual(layout.root.clientWidth)

    expect(layout.detail.top).toBeGreaterThanOrEqual(layout.menu.bottom)
    expect(Math.abs(layout.detail.left - layout.menu.left)).toBeLessThan(1)
    expect(Math.abs(layout.detail.width - layout.menu.width)).toBeLessThan(1)
    expect(layout.heading.bottom).toBeLessThan(844)
    expect(layout.summary.bottom).toBeLessThan(844)
    expect(layout.summary.fontSize).toBeGreaterThanOrEqual(14)

    expect(layout.menuButtons).toHaveLength(5)
    for (const button of layout.menuButtons) {
      expect(button.fontSize).toBeGreaterThanOrEqual(11)
      expect(button.height).toBeGreaterThanOrEqual(48)
      expect(button.touchAction).toBe('manipulation')
    }
    for (const control of layout.interactive) {
      expect(control.height, `${control.text} touch height`).toBeGreaterThanOrEqual(48)
    }

    expect(layout.canvas.position).toBe('fixed')
    expect(layout.canvas.top).toBe(0)
    expect(layout.canvas.left).toBe(0)
    expect(layout.canvas.width).toBe(390)
    expect(layout.canvas.height).toBe(844)

    const root = page.locator('#root')
    await root.evaluate((element) => element.scrollTo({ top: 320 }))
    await expect.poll(() => root.evaluate((element) => element.scrollTop)).toBeGreaterThan(0)
    const scrolledCanvas = await page.locator('.world-canvas').evaluate((element) => ({
      position: getComputedStyle(element).position,
      top: element.getBoundingClientRect().top,
    }))
    expect(scrolledCanvas).toEqual({ position: 'fixed', top: 0 })
  })

  test('keeps semantic keyboard and touch selection in sync', async ({ page }) => {
    await page.goto(PAGE_PATH)

    await page.keyboard.press('Tab')
    await expect(page.getByRole('button', { name: 'KANTO FIRST PERSON' })).toBeFocused()

    await page.keyboard.press('ArrowDown')
    await expect(page.getByRole('button', { name: 'FIELD FEATURES' })).toHaveAttribute('aria-current', 'page')
    await expect(page.getByRole('button', { name: 'FIELD FEATURES' })).toBeFocused()
    await expect(page.getByRole('heading', { name: 'The world gets bigger.' })).toBeVisible()

    await page.keyboard.press('Enter')
    await expect(page.getByRole('button', { name: 'FIELD FEATURES' })).toHaveAttribute('aria-current', 'page')

    await page.keyboard.press('x')
    await expect(page.getByRole('button', { name: 'KANTO FIRST PERSON' })).toHaveAttribute('aria-current', 'page')
    await expect(page.getByRole('button', { name: 'KANTO FIRST PERSON' })).toBeFocused()

    await page.getByRole('button', { name: 'SUPPORT CENTER' }).click()
    await expect(page.getByRole('button', { name: 'SUPPORT CENTER' })).toHaveAttribute('aria-current', 'page')
    await expect(page.getByRole('heading', { name: 'Evidence before guesses.' })).toBeVisible()

    await page.getByRole('button', { name: 'Y', exact: true }).click()
    await expect(page.locator('.app')).toHaveClass(/edition-yellow/)
    await expect(page.getByRole('button', { name: 'Y', exact: true })).toHaveAttribute('aria-pressed', 'true')
  })
})

test('preserves the desktop two-column terminal and fixed scene', async ({ page }) => {
  await page.setViewportSize({ width: 1440, height: 900 })
  await page.goto(PAGE_PATH)

  const layout = await page.evaluate(() => {
    const box = (rect: DOMRect) => ({
      bottom: rect.bottom,
      height: rect.height,
      left: rect.left,
      right: rect.right,
      top: rect.top,
      width: rect.width,
    })
    const menu = document.querySelector<HTMLElement>('.menu-window')!
    const detail = document.querySelector<HTMLElement>('.detail-window')!
    const canvas = document.querySelector<HTMLElement>('.world-canvas')!
    const root = document.querySelector<HTMLElement>('#root')!
    return {
      menu: box(menu.getBoundingClientRect()),
      detail: box(detail.getBoundingClientRect()),
      menuDisplay: getComputedStyle(menu).display,
      canvas: {
        ...box(canvas.getBoundingClientRect()),
        position: getComputedStyle(canvas).position,
      },
      rootOverflow: getComputedStyle(root).overflow,
    }
  })

  expect(layout.menuDisplay).toBe('flex')
  expect(layout.menu.right).toBeLessThan(layout.detail.left)
  expect(Math.abs(layout.menu.top - layout.detail.top)).toBeLessThan(1)
  expect(Math.abs(layout.menu.height - layout.detail.height)).toBeLessThan(1)
  expect(layout.rootOverflow).toBe('hidden')
  expect(layout.canvas.position).toBe('fixed')
  expect(layout.canvas.width).toBe(1440)
  expect(layout.canvas.height).toBe(900)
})
