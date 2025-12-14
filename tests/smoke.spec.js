// @ts-check
const { test, expect } = require('@playwright/test');

test.describe('SPA Smoke Tests', () => {

    test('Home page loads', async ({ page }) => {
        await page.goto('/');
        await expect(page.getByTestId('page-home')).toBeVisible();
    });

    test('Accounts page loads', async ({ page }) => {
        await page.goto('/accounts');
        await expect(page.getByTestId('page-accounts')).toBeVisible();
        await expect(page.getByTestId('accounts-table')).toBeVisible();
    });

    test('Proxies page loads', async ({ page }) => {
        await page.goto('/proxies');
        await expect(page.getByTestId('page-proxies')).toBeVisible();
        await expect(page.getByTestId('proxies-table')).toBeVisible();
    });

    test('Autosubscribe page loads', async ({ page }) => {
        await page.goto('/subscriber');
        await expect(page.getByTestId('page-autosubscribe')).toBeVisible();
        await expect(page.getByTestId('autosubscribe-start-btn')).toBeVisible();
    });

    test('Parser page loads', async ({ page }) => {
        await page.goto('/parser');
        await expect(page.getByTestId('page-parser')).toBeVisible();
        await expect(page.getByTestId('parser-search-btn')).toBeVisible();
    });

    test('Dashboard page loads', async ({ page }) => {
        await page.goto('/dashboard');
        await expect(page.getByTestId('page-dashboard')).toBeVisible();
        await expect(page.getByTestId('dashboard-stats')).toBeVisible();
    });

    test('Templates page loads', async ({ page }) => {
        await page.goto('/templates');
        await expect(page.getByTestId('page-templates')).toBeVisible();
        await expect(page.getByTestId('templates-list')).toBeVisible();
    });

    test('Channels page loads', async ({ page }) => {
        await page.goto('/channels');
        await expect(page.getByTestId('page-channels')).toBeVisible();
        await expect(page.getByTestId('channels-table')).toBeVisible();
    });

    test('Settings page loads', async ({ page }) => {
        await page.goto('/settings');
        await expect(page.getByTestId('page-settings')).toBeVisible();
    });

    test('Navigation smoke test', async ({ page }) => {
        const consoleErrors = [];
        page.on('console', msg => {
            if (msg.type() === 'error') {
                consoleErrors.push(msg.text());
            }
        });

        await page.goto('/');
        await expect(page.getByTestId('page-home')).toBeVisible();

        // Accounts
        await page.getByTestId('nav-accounts').click();
        await expect(page.getByTestId('page-accounts')).toBeVisible();

        // Proxies
        await page.getByTestId('nav-proxies').click();
        await expect(page.getByTestId('page-proxies')).toBeVisible();

        // Autosubscribe
        await page.getByTestId('nav-autosubscribe').click();
        await expect(page.getByTestId('page-autosubscribe')).toBeVisible();

        // Parser
        await page.getByTestId('nav-parser').click();
        await expect(page.getByTestId('page-parser')).toBeVisible();

        // Dashboard
        await page.getByTestId('nav-dashboard').click();
        await expect(page.getByTestId('page-dashboard')).toBeVisible();

        // Templates
        await page.getByTestId('nav-templates').click();
        await expect(page.getByTestId('page-templates')).toBeVisible();

        // Channels
        await page.getByTestId('nav-channels').click();
        await expect(page.getByTestId('page-channels')).toBeVisible();

        // Settings
        await page.getByTestId('nav-settings').click();
        await expect(page.getByTestId('page-settings')).toBeVisible();

        expect(consoleErrors).toEqual([]);
    });

});
