import { expect, test, type Page, type Route } from '@playwright/test'

const baseTracking = {
  id: 1,
  tracking_number: '1024658760',
  enabled: true,
  notes: null,
  baseline_initialized: false,
  shipment_id: null,
  client_reference: null,
  outer_carrier_code: null,
  outer_carrier_tracking_number: null,
  shipment_status: null,
  localized_status: '暂无状态',
  country: null,
  postcode: null,
  parcel_count: null,
  last_checked_at: null,
  last_success_at: null,
  last_error: null,
  recipients: [],
  traces: [],
}

async function json(route: Route, body: unknown, status = 200) {
  await route.fulfill({ status, contentType: 'application/json', body: JSON.stringify(body) })
}

async function mockApi(page: Page) {
  let loggedIn = false
  let trackings: typeof baseTracking[] = []
  const recipients: Array<{ id: number; name: string; email: string; enabled: boolean; tracking_count: number }> = []
  let interval = 30

  await page.route('**/api/v1/**', async (route) => {
    const request = route.request()
    const url = new URL(request.url())
    const path = url.pathname.replace('/api/v1', '')
    const method = request.method()

    if (path === '/auth/me') return json(route, loggedIn ? { id: 1, username: 'admin' } : { detail: 'Not authenticated' }, loggedIn ? 200 : 401)
    if (path === '/auth/csrf') return json(route, { csrf_token: 'e2e-csrf-token' })
    if (path === '/auth/login' && method === 'POST') { loggedIn = true; return json(route, { id: 1, username: 'admin', csrf_token: 'e2e-csrf-token' }) }
    if (path === '/trackings' && method === 'GET') return json(route, { items: trackings, total: trackings.length, page: 1, page_size: 20 })
    if (path === '/trackings' && method === 'POST') {
      const body = request.postDataJSON() as { tracking_number: string }
      trackings = [{ ...baseTracking, tracking_number: body.tracking_number }]
      return json(route, trackings[0], 201)
    }
    if (/^\/trackings\/\d+\/query$/.test(path) && method === 'POST') {
      trackings = trackings.map((item) => ({ ...item, baseline_initialized: true, shipment_status: 'in_transit', localized_status: '运输中', last_checked_at: '2026-08-08T10:00:00Z' }))
      return json(route, { job_run_id: 1, status: 'completed', total_count: 1, success_count: 1, failure_count: 0, changed_count: 0 })
    }
    if (/^\/trackings\/\d+$/.test(path) && method === 'PATCH') return json(route, trackings[0])
    if (path === '/recipients' && method === 'GET') return json(route, { items: recipients, total: recipients.length })
    if (path === '/recipients' && method === 'POST') {
      const body = request.postDataJSON() as { name: string; email: string; enabled: boolean }
      recipients.push({ id: 1, ...body, tracking_count: 0 })
      return json(route, recipients[0], 201)
    }
    if (path === '/settings/schedule' && method === 'GET') return json(route, { enabled: true, interval_minutes: interval, timezone: 'Asia/Shanghai' })
    if (path === '/settings/schedule' && method === 'PUT') { interval = (request.postDataJSON() as { interval_minutes: number }).interval_minutes; return json(route, { enabled: true, interval_minutes: interval, timezone: 'Asia/Shanghai' }) }
    if (path === '/settings/smtp' && method === 'GET') return json(route, { host: null, port: null, security: null, username: null, sender_name: null, sender_email: null, password_configured: false })
    if (path === '/runs' && method === 'GET') return json(route, { items: [{ id: 1, trigger: 'manual', status: 'partial', started_at: '2026-08-08T10:00:00Z', finished_at: '2026-08-08T10:00:02Z', total_count: 1, success_count: 1, failure_count: 0, changed_count: 0, error_summary: null }], total: 1, page: 1, page_size: 20 })
    if (path === '/runs/1' && method === 'GET') return json(route, { id: 1, trigger: 'manual', status: 'partial', started_at: '2026-08-08T10:00:00Z', finished_at: '2026-08-08T10:00:02Z', total_count: 1, success_count: 1, failure_count: 0, changed_count: 0, error_summary: null, items: [{ id: 1, tracking_item_id: 1, tracking_number: '1024658760', status: 'succeeded', changed: false, added_event_count: 1, previous_status: null, current_status: 'in_transit', error: null, checked_at: '2026-08-08T10:00:00Z' }], notifications: [{ id: 8, recipient_email: 'alice@example.com', subject: '物流更新', status: 'failed', attempt_count: 6, next_attempt_at: null, last_error: 'SMTP unavailable', created_at: '2026-08-08T10:00:00Z', sent_at: null }] })
    if (path === '/notifications/8/retry' && method === 'POST') return json(route, { notification_id: 8, selected: 1, sent: 1, failed: 0 })
    return json(route, { detail: `Unhandled ${method} ${path}` }, 500)
  })
}

test('管理员完成核心管理流程', async ({ page }) => {
  await mockApi(page)
  await page.goto('/login')
  await page.getByLabel('管理员账号').fill('admin')
  await page.getByLabel('密码', { exact: true }).fill('initial-password-123')
  await page.getByRole('button', { name: '登录', exact: true }).click()
  await expect(page.getByRole('heading', { name: '运行概览' })).toBeVisible()

  await page.getByRole('link', { name: '运单管理' }).click()
  await page.getByRole('button', { name: '添加运单' }).click()
  await page.getByLabel('运单号').fill('1024658760')
  await page.getByRole('button', { name: '保存', exact: true }).click()
  await expect(page.getByText('1024658760')).toBeVisible()
  await page.getByRole('button', { name: '查询', exact: true }).click()
  await expect(page.getByText('查询完成：成功 1，失败 0')).toBeVisible()

  await page.getByRole('link', { name: '收件人' }).click()
  await page.getByRole('button', { name: '添加收件人' }).click()
  await page.getByLabel('姓名').fill('Alice')
  await page.getByLabel('邮箱').fill('alice@example.com')
  await page.getByLabel('1024658760').check()
  await page.getByRole('button', { name: '保存', exact: true }).click()
  await expect(page.getByText('alice@example.com')).toBeVisible()

  await page.getByRole('link', { name: '系统设置' }).click()
  await page.getByLabel('查询间隔（分钟）').fill('45')
  await page.getByRole('button', { name: '保存调度设置' }).click()
  await expect(page.getByText('调度设置已保存')).toBeVisible()

  await page.getByRole('link', { name: '运行记录' }).click()
  await page.getByText('#1').click()
  await expect(page.getByText('SMTP unavailable')).toBeVisible()
  page.once('dialog', (dialog) => dialog.accept())
  await page.getByRole('button', { name: '重试' }).click()
  await expect(page.getByText('邮件已成功发送')).toBeVisible()
})
