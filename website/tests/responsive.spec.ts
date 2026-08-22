import { expect, test } from '@playwright/test'

const PAGE_PATH = '/kanto-first-person/'

test.describe('mobile field terminal', () => {
  test.use({ viewport: { width: 390, height: 844 } })

  test('is readable, touch-friendly, stacked, and scrollable', async ({ page }, testInfo) => {
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

    expect(layout.menuButtons).toHaveLength(7)
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

    await page.screenshot({ path: testInfo.outputPath('mobile-menu.png'), fullPage: true })
    const root = page.locator('#root')
    await root.evaluate((element) => element.scrollTo({ top: 320 }))
    await expect.poll(() => root.evaluate((element) => element.scrollTop)).toBeGreaterThan(0)
    const scrolledCanvas = page.locator('.world-canvas')
    await expect(scrolledCanvas).toHaveCSS('position', 'fixed')
    await expect.poll(() => scrolledCanvas.evaluate((element) => element.getBoundingClientRect().top)).toBe(0)
  })

  test('keeps semantic keyboard and touch selection in sync', async ({ page }) => {
    await page.goto(PAGE_PATH)

    await page.keyboard.press('Tab')
    await expect(page.getByRole('link', { name: /BUILD 11\/11 PASS/ })).toBeFocused()
    await page.keyboard.press('Tab')
    await expect(page.getByRole('link', { name: /SOURCE 5e8544f/ })).toBeFocused()
    await page.keyboard.press('Tab')
    await expect(page.getByRole('button', { name: 'KANTO FIRST PERSON' })).toBeFocused()

    await page.keyboard.press('ArrowDown')
    await expect(page.getByRole('button', { name: 'FIELD FEATURES' })).toHaveAttribute('aria-current', 'page')
    await expect(page.getByRole('button', { name: 'FIELD FEATURES' })).toBeFocused()
    await expect(page.getByRole('heading', { name: 'The world gets bigger.' })).toBeVisible()

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
    const banner = document.querySelector<HTMLElement>('.release-banner')!
    const canvas = document.querySelector<HTMLElement>('.world-canvas')!
    const root = document.querySelector<HTMLElement>('#root')!
    return {
      banner: box(banner.getBoundingClientRect()),
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
  expect(layout.banner.bottom).toBeLessThan(layout.menu.top)
  expect(layout.menu.right).toBeLessThan(layout.detail.left)
  expect(Math.abs(layout.menu.top - layout.detail.top)).toBeLessThan(1)
  expect(Math.abs(layout.menu.height - layout.detail.height)).toBeLessThan(1)
  expect(layout.rootOverflow).toBe('hidden')
  expect(layout.canvas.position).toBe('fixed')
  expect(layout.canvas.width).toBe(1440)
  expect(layout.canvas.height).toBe(900)
  await expect(page.locator('.world-pokeballs')).toHaveAttribute('data-scene-mode', 'pokeballs-only')
  await expect(page.locator('.world-pokeballs')).toHaveAttribute('data-menu-reactive', 'false')
  await expect(page.locator('.world-pokeballs')).toHaveAttribute('data-ball-count', '11')
  await expect(page.locator('.world-pokeballs')).toHaveAttribute('data-ball-size-variants', '4')
  await page.getByRole('button', { name: 'Effects quality high' }).click()
  await expect(page.locator('.world-pokeballs')).toHaveAttribute('data-ball-count', '6')
})

test('keeps the home vital labels fully visible', async ({ page }) => {
  await page.setViewportSize({ width: 1440, height: 900 })
  await page.goto(PAGE_PATH)

  const metrics = await page.locator('.home-vitals small').evaluateAll((labels) => labels.map((label) => {
    const labelBox = label.getBoundingClientRect()
    const cellBox = label.parentElement!.getBoundingClientRect()
    const style = getComputedStyle(label)
    return {
      bottomInsideCell: labelBox.bottom <= cellBox.bottom,
      fontSize: Number.parseFloat(style.fontSize),
      lineHeight: Number.parseFloat(style.lineHeight),
      overflow: style.overflow,
      topInsideCell: labelBox.top >= cellBox.top,
    }
  }))

  expect(metrics).toHaveLength(3)
  for (const label of metrics) {
    expect(label.topInsideCell).toBe(true)
    expect(label.bottomInsideCell).toBe(true)
    expect(label.overflow).toBe('visible')
    expect(label.fontSize).toBeGreaterThanOrEqual(7.5)
    expect(label.lineHeight).toBeGreaterThan(label.fontSize)
  }
})

test('keeps the verified coming-soon status above every menu page', async ({ page }) => {
  await page.setViewportSize({ width: 1440, height: 900 })
  await page.goto(PAGE_PATH)

  const banner = page.getByRole('region', { name: 'COMING SOON' })
  await expect(banner).toContainText('2.0.0-alpha.1')
  await expect(banner).toContainText('11/11 PASS')
  await expect(banner).toContainText('5e8544f')
  await expect(banner).toContainText('NOT RELEASED')
  await expect(banner.getByText(/SYNCED 2026-08-22/)).toBeVisible()
  await expect(banner.getByRole('link', { name: /SOURCE 5e8544f/ })).toHaveAttribute('href', /commit\/5e8544f/)

  const routes = ['features', 'activity', 'guide', 'support', 'rebuild', 'github']
  for (const [index, route] of routes.entries()) {
    await page.evaluate((hash) => { window.location.hash = hash }, route)
    await expect(page.locator('.menu-window > button').nth(index + 1)).toHaveAttribute('aria-current', 'page')
    await expect(banner).toBeVisible()
  }
})

test('shows verified work as a game-style research log on the homepage', async ({ page }) => {
  await page.setViewportSize({ width: 1440, height: 900 })
  await page.goto(PAGE_PATH)

  const log = page.getByRole('region', { name: 'OAK RESEARCH LOG' })
  await expect(log).toBeVisible()
  await expect(log).toContainText('WORK CONTINUES')
  await expect(log).toContainText('FIELD NOTES')
  await expect(log).toContainText('NEW MOVE')
  await expect(log).toContainText('RESEARCH UPDATE')
  await expect(log.getByRole('link', { name: /Merge pull request #11/ })).toHaveAttribute('href', /commit\/5e8544f/)
  await expect(log.getByRole('link', { name: /OPEN FULL LOG/ })).toHaveAttribute('href', '#activity')

  const clock = page.getByRole('region', { name: 'Trainer Clock' })
  await expect(clock).toContainText('LAST UPDATE')
  await expect(clock).toContainText('LATEST CI TIME')
  await expect(clock).toContainText('50S')
  await expect(clock).toContainText('DEPLOYED')
  await expect(clock).toContainText('7-DAY COMMITS')

  const latest = log.locator('ol > li').first()
  await expect(latest).toContainText('LIVE')
  await expect(latest).toContainText('CI 50S')
  const timestamp = latest.getByRole('button', { name: /ago|just now/i })
  await expect(timestamp).toHaveAttribute('title', /2026/)
  await timestamp.focus()
  await expect(latest.getByRole('tooltip')).toBeVisible()
  await timestamp.click()
  await expect(timestamp).toHaveAttribute('aria-expanded', 'true')
  await expect(latest.getByRole('tooltip')).toHaveCSS('opacity', '1')
})

test('shows automatic project time and PR task timing without claiming work hours', async ({ page }) => {
  await page.setViewportSize({ width: 1440, height: 900 })
  await page.goto(PAGE_PATH)

  const stats = page.getByRole('region', { name: 'VERIFIED DEV STATS' })
  await expect(stats).toContainText('PROJECT AGE')
  await expect(stats).toContainText('ACTIVE DAYS')
  await expect(stats).toContainText('MERGED TASKS')
  await expect(stats).toContainText('TOTAL CI TIME')
  await expect(stats).toContainText('26M 51S')
  await expect(stats).toContainText('MEDIAN PR TIME')
  await expect(stats).toContainText('59S')
  await expect(stats).toContainText('AI TOKENS')
  await expect(stats).toContainText('NOT TRACKED')
  await expect(stats).toContainText('AI TOKENS ARE PRIVATE AND NOT EXPORTED')
  await expect(stats).toContainText('NOT HANDS-ON HOURS')

  const quests = stats.locator('.quest-log > li')
  await expect(quests).toHaveCount(3)
  await expect(quests.first()).toContainText('QUEST #11')
  await expect(quests.first()).toContainText('PR TIME 3M 2S')
  await expect(quests.first().getByRole('link')).toHaveAttribute('href', /pull\/11$/)

  await page.goto(`${PAGE_PATH}#activity`)
  const fullStats = page.getByRole('region', { name: 'VERIFIED DEV STATS' })
  await expect(fullStats).toContainText('COMPLETE MERGED TASK HISTORY')
  await expect(fullStats.locator('.quest-log > li')).toHaveCount(11)
})

test('shows the complete verified project history in the Research Log', async ({ page }) => {
  await page.setViewportSize({ width: 1440, height: 900 })
  await page.goto(`${PAGE_PATH}#activity`)

  await expect(page.getByRole('button', { name: 'RESEARCH LOG' })).toHaveAttribute('aria-current', 'page')
  const menuButtons = page.locator('.menu-window > button')
  await expect(menuButtons.nth(1)).toContainText('FIELD FEATURES')
  await expect(menuButtons.nth(2)).toContainText('RESEARCH LOG')
  await expect(page.getByRole('heading', { name: 'Every step. No mystery.' })).toBeVisible()
  const vitals = page.locator('[aria-label="Complete development totals"]')
  await expect(vitals.getByText('110', { exact: true })).toBeVisible()
  await expect(vitals.getByText('VERIFIED COMMITS')).toBeVisible()
  await expect(vitals.getByText('2', { exact: true })).toBeVisible()
  await expect(vitals.getByText('CONTRIBUTORS')).toBeVisible()
  const rewriteDate = vitals.getByLabel('Rewrite began 2026-08-21')
  await expect(rewriteDate).toHaveAttribute('datetime', '2026-08-21')
  await expect(rewriteDate).toHaveText('AUG 21')
  await expect(vitals.getByText('REWRITE BEGAN / 2026')).toBeVisible()

  const milestones = page.getByRole('region', { name: 'FIELD BADGES' })
  await expect(milestones).toContainText('NO MANUAL LOGGING REQUIRED')
  await expect(milestones.getByRole('link')).toHaveCount(6)

  const ledger = page.getByRole('region', { name: 'COMPLETE VERIFIED HISTORY' })
  await expect(ledger.locator('ol > li')).toHaveCount(110)
  await expect(ledger.getByRole('link', { name: /Merge pull request #11/ })).toHaveAttribute('href', /commit\/5e8544f/)
  await expect(ledger.getByRole('link', { name: /140bcc7/ })).toHaveAttribute('href', /commit\/140bcc7/)
  await expect(ledger.locator('ol > li').first()).toContainText('LIVE')
  await expect(ledger).toContainText('TODAY')
  await expect(ledger).toContainText('ARCHIVED')

  const systemMap = page.getByRole('img', { name: /Diagram showing commits/ })
  await expect(systemMap).toBeVisible()
  await expect.poll(() => systemMap.evaluate((image: HTMLImageElement) => image.naturalWidth)).toBe(1600)
  await expect(page.getByRole('link', { name: /DOWNLOAD SHARE GRAPHIC/ })).toHaveAttribute('href', /activity-system-share\.png$/)
})

test('keeps Trainer Clock and commit timing controls readable at desktop and mobile widths', async ({ page }) => {
  for (const width of [1440, 901, 390]) {
    await page.setViewportSize({ width, height: 900 })
    await page.goto(PAGE_PATH)

    const clock = page.getByRole('region', { name: 'Trainer Clock' })
    const log = page.getByRole('region', { name: 'OAK RESEARCH LOG' })
    await expect(clock).toBeVisible()
    await expect(log).toBeVisible()

    const fit = await page.locator('.trainer-clock, .activity-log').evaluateAll((items) => items.map((item) => ({
      clipped: item.scrollWidth > item.clientWidth + 1,
      pageOverflow: document.documentElement.scrollWidth > document.documentElement.clientWidth + 1,
    })))
    expect(fit, `timing UI must fit at ${width}px`).toEqual(
      fit.map(() => ({ clipped: false, pageOverflow: false })),
    )

    const trigger = log.locator('.timestamp-trigger').first()
    const box = await trigger.evaluate((element) => {
      const rect = element.getBoundingClientRect()
      return { width: rect.width, height: rect.height }
    })
    expect(box.height).toBeGreaterThanOrEqual(48)
  }
})

test('keeps the dev stats save file readable at desktop and mobile widths', async ({ page }, testInfo) => {
  for (const width of [1440, 901, 390]) {
    await page.setViewportSize({ width, height: 900 })
    await page.goto(PAGE_PATH)

    const stats = page.getByRole('region', { name: 'VERIFIED DEV STATS' })
    await expect(stats).toBeVisible()
    const fit = await stats.evaluate((element) => ({
      clipped: element.scrollWidth > element.clientWidth + 1,
      pageOverflow: document.documentElement.scrollWidth > document.documentElement.clientWidth + 1,
      statText: [...element.querySelectorAll<HTMLElement>('dt, dd')].map((item) => ({
        text: item.textContent?.trim(),
        clipped: item.scrollWidth > item.clientWidth + 1,
      })),
      questLinks: [...element.querySelectorAll<HTMLElement>('.quest-log a')].map((link) => ({
        height: link.getBoundingClientRect().height,
        clipped: link.scrollWidth > link.clientWidth + 1,
      })),
      questDurations: [...element.querySelectorAll<HTMLElement>('.quest-duration')].map((duration) => ({
        text: duration.textContent?.trim(),
        clipped: duration.scrollWidth > duration.clientWidth + 1,
        fontSize: Number.parseFloat(getComputedStyle(duration).fontSize),
        fontFamily: getComputedStyle(duration).fontFamily,
      })),
    }))

    expect(fit.clipped, `dev stats must fit at ${width}px`).toBe(false)
    expect(fit.pageOverflow, `page must not overflow at ${width}px`).toBe(false)
    for (const item of fit.statText) {
      expect(item.clipped, `${item.text} must fit at ${width}px`).toBe(false)
    }
    for (const link of fit.questLinks) {
      expect(link.height).toBeGreaterThanOrEqual(48)
      expect(link.clipped).toBe(false)
    }
    for (const duration of fit.questDurations) {
      expect(duration.clipped, `${duration.text} must fit at ${width}px`).toBe(false)
      expect(duration.fontSize, `${duration.text} must remain readable at ${width}px`).toBeGreaterThanOrEqual(9.5)
      expect(duration.fontFamily).toContain('ui-monospace')
    }

    if (width === 1440 || width === 390) {
      await stats.screenshot({
        path: testInfo.outputPath(`dev-stats-${width}.png`),
      })
    }
  }
})

test('keeps the verified rewrite start date readable at desktop and mobile widths', async ({ page }) => {
  for (const width of [1440, 901, 390]) {
    await page.setViewportSize({ width, height: 900 })
    await page.goto(`${PAGE_PATH}#activity`)

    const card = page.locator('.archive-date-vital')
    const fit = await card.evaluate((element) => {
      const value = element.querySelector('b') as HTMLElement
      const label = element.querySelector('span') as HTMLElement
      const cardBox = element.getBoundingClientRect()
      const valueBox = value.getBoundingClientRect()
      const labelBox = label.getBoundingClientRect()
      return {
        valueFits: value.scrollWidth <= value.clientWidth + 1
          && valueBox.right <= cardBox.right + 1,
        labelFits: label.scrollWidth <= label.clientWidth + 1
          && labelBox.right <= cardBox.right + 1,
      }
    })

    expect(fit, `rewrite date card must fit at ${width}px`).toEqual({ valueFits: true, labelFits: true })
  }
})

test('keeps field badge numbers clear of milestone titles', async ({ page }) => {
  for (const width of [1440, 901, 390]) {
    await page.setViewportSize({ width, height: 900 })
    await page.goto(`${PAGE_PATH}#activity`)

    const cards = page.locator('.milestone-deck a')
    await expect(cards).toHaveCount(6)
    const layout = await cards.evaluateAll((items) => items.map((card) => {
      const badge = card.querySelector('i') as HTMLElement
      const title = card.querySelector('b') as HTMLElement
      const badgeBox = badge.getBoundingClientRect()
      const titleBox = title.getBoundingClientRect()
      return {
        overlap: !(titleBox.right <= badgeBox.left
          || titleBox.left >= badgeBox.right
          || titleBox.bottom <= badgeBox.top
          || titleBox.top >= badgeBox.bottom),
        titleClipped: title.scrollWidth > title.clientWidth + 1
          || title.scrollHeight > title.clientHeight + 1,
      }
    }))

    expect(layout, `field badges must fit at ${width}px`).toEqual(
      layout.map(() => ({ overlap: false, titleClipped: false })),
    )
  }
})

test('keeps every activity translation label inside its graphic card', async ({ page }) => {
  await page.goto(`${PAGE_PATH}activity-system-share.svg`)

  const cards = page.locator('.translation-card')
  await expect(cards).toHaveCount(6)
  const fit = await cards.evaluateAll((items) => items.map((card) => {
    const rect = card.querySelector('rect') as SVGGraphicsElement
    const label = card.querySelector('.translation-label') as SVGGraphicsElement
    const cardBox = rect.getBBox()
    const labelBox = label.getBBox()
    return {
      text: label.textContent,
      fitsLeft: labelBox.x >= cardBox.x + 12,
      fitsRight: labelBox.x + labelBox.width <= cardBox.x + cardBox.width - 12,
    }
  }))

  expect(fit).toEqual(fit.map((entry) => ({ ...entry, fitsLeft: true, fitsRight: true })))
})

test('supports shareable hash routes and browser history', async ({ page }) => {
  await page.setViewportSize({ width: 1440, height: 900 })
  await page.goto(`${PAGE_PATH}#rebuild`)

  await expect(page.getByRole('button', { name: 'NEXT-GEN REBUILD' })).toHaveAttribute('aria-current', 'page')
  await expect(page.getByRole('heading', { name: 'Same Kanto. New foundations.' })).toBeVisible()

  await page.getByRole('button', { name: 'SUPPORT CENTER' }).click()
  await expect(page).toHaveURL(/#support$/)
  await expect(page.getByRole('heading', { name: 'Evidence before guesses.' })).toBeVisible()

  await page.goBack()
  await expect(page).toHaveURL(/#rebuild$/)
  await expect(page.getByRole('heading', { name: 'Same Kanto. New foundations.' })).toBeVisible()
})

test('publishes social preview metadata and labels concept media honestly', async ({ page }) => {
  await page.setViewportSize({ width: 1440, height: 900 })
  await page.goto(`${PAGE_PATH}#rebuild`)

  await expect(page.locator('meta[property="og:image"]')).toHaveAttribute('content', /og-kanto-rebuild\.png$/)
  const concept = page.getByRole('img', { name: /Original pixel-art concept/ })
  await expect(concept).toBeVisible()
  await expect(page.getByText('CONCEPT ART // NOT GAMEPLAY')).toBeVisible()
  await expect(page.getByText('REAL FOOTAGE UNLOCKS AFTER ACCEPTANCE')).toBeVisible()
  await expect.poll(() => concept.evaluate((image: HTMLImageElement) => image.naturalWidth)).toBeGreaterThan(0)
})

test('explains the rewrite with an architecture evolution scan and verified upgrades', async ({ page }) => {
  await page.setViewportSize({ width: 1440, height: 900 })
  await page.goto(PAGE_PATH)
  await page.getByRole('button', { name: 'NEXT-GEN REBUILD' }).click()

  await expect(page.getByRole('heading', { name: 'Same Kanto. New foundations.' })).toBeVisible()
  await expect(page.getByText('REWRITE EVOLUTION SCAN')).toBeVisible()
  await expect(page.getByText('OLD: MOD MUTATES HOST')).toBeVisible()
  await expect(page.getByText('NEW: HOST VALIDATES PACKETS')).toBeVisible()
  await expect(page.locator('.concept-scene')).toHaveCount(0)
  await expect(page.getByText('V1.60')).toBeVisible()
  await expect(page.getByText('V2.0')).toBeVisible()
  await expect(page.getByText('PUBLIC COMPANION API')).toBeVisible()
  await expect(page.getByText('BUDGETED COMPILER')).toBeVisible()
  await expect(page.getByText('53')).toBeVisible()
  await expect(page.getByRole('link', { name: /EXPLORE THE ARCHITECTURE/ })).toHaveAttribute('href', /docs\/architecture\.md$/)
})

test('uses standard desktop open and back keys', async ({ page }) => {
  await page.setViewportSize({ width: 1440, height: 900 })
  await page.goto(PAGE_PATH)

  await page.keyboard.press('Tab')
  await expect(page.getByRole('link', { name: /BUILD/ })).toBeFocused()
  await page.keyboard.press('Tab')
  await expect(page.getByRole('link', { name: /SOURCE/ })).toBeFocused()
  await page.keyboard.press('Tab')
  await expect(page.getByRole('button', { name: 'KANTO FIRST PERSON' })).toBeFocused()
  await page.keyboard.press('ArrowDown')

  const enterPopupPromise = page.waitForEvent('popup')
  await page.keyboard.press('Enter')
  const enterPopup = await enterPopupPromise
  await expect(enterPopup).toHaveURL(/\/docs\/feature-parity\.md$/)
  await enterPopup.close()

  const spacePopupPromise = page.waitForEvent('popup')
  await page.keyboard.press('Space')
  const spacePopup = await spacePopupPromise
  await expect(spacePopup).toHaveURL(/\/docs\/feature-parity\.md$/)
  await spacePopup.close()

  await page.keyboard.press('Escape')
  await expect(page.getByRole('button', { name: 'KANTO FIRST PERSON' })).toHaveAttribute('aria-current', 'page')
  await expect(page.getByRole('button', { name: 'KANTO FIRST PERSON' })).toBeFocused()
})
