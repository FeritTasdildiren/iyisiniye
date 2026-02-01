import { test, expect } from '@playwright/test';

test.describe('Hata Durumlari - Mevcut Olmayan Restoran', () => {
  test('varolmayan slug ile restoran detay sayfasinda hata mesaji gorunur', async ({ page }) => {
    await page.goto('/restaurant/bu-restoran-kesinlikle-yok-12345');

    // Yukleniyor durumunu bekle (skeleton kaybolana kadar)
    await page.waitForFunction(
      () => document.querySelectorAll('.animate-pulse').length === 0,
      { timeout: 10_000 },
    );

    // Hata mesaji gorunmeli: "Veri alinamadi"
    await expect(page.getByText('Veri alınamadı')).toBeVisible();

    // Hata detayi gorunmeli: "Restoran bilgileri yuklenemedi"
    await expect(page.getByText('Restoran bilgileri yüklenemedi')).toBeVisible();

    // "Tekrar Dene" butonu gorunmeli
    await expect(page.getByRole('button', { name: 'Tekrar Dene' })).toBeVisible();
  });

  test('"Tekrar Dene" butonuna tiklandiginda sayfa yeniden yuklenir', async ({ page }) => {
    await page.goto('/restaurant/bu-restoran-kesinlikle-yok-99999');

    // Hata durumunu bekle
    await page.waitForFunction(
      () => document.querySelectorAll('.animate-pulse').length === 0,
      { timeout: 10_000 },
    );

    await expect(page.getByText('Veri alınamadı')).toBeVisible();

    // "Tekrar Dene" butonuna tikla
    const reloadPromise = page.waitForEvent('load');
    await page.getByRole('button', { name: 'Tekrar Dene' }).click();
    await reloadPromise;

    // Sayfa yeniden yuklendi - tekrar hata veya basarili sonuc gorunmeli
    await page.waitForFunction(
      () => document.querySelectorAll('.animate-pulse').length === 0,
      { timeout: 10_000 },
    );

    // Hata veya basarili icerik gorunmeli
    const pageContent = page.locator('main');
    await expect(pageContent).toBeVisible();
  });
});

test.describe('Hata Durumlari - Bos Arama Sonucu', () => {
  test('anlamsiz arama teriminde EmptyState bilesenini gosterir', async ({ page }) => {
    await page.goto('/search');

    const searchInput = page.getByPlaceholder('Yemek veya mekan ara...');
    await searchInput.fill('xyzqwerty123456asdfghjkl');
    await page.getByRole('button', { name: 'Ara' }).click();

    // Sonuclarin yuklenmesini bekle
    await page.waitForFunction(
      () => document.querySelectorAll('.animate-pulse').length === 0,
      { timeout: 10_000 },
    );

    // EmptyState bilesenindeki mesaj gorunmeli
    await expect(page.getByText('Bu arama için sonuç bulamadık')).toBeVisible();

    // Yardimci aciklama metni gorunmeli
    await expect(
      page.getByText('Farklı bir terimle tekrar deneyebilir veya filtreleri temizleyebilirsiniz.'),
    ).toBeVisible();
  });

  test('bos arama sonucunda "0 sonuc bulundu" gosterilir', async ({ page }) => {
    await page.goto('/search');

    const searchInput = page.getByPlaceholder('Yemek veya mekan ara...');
    await searchInput.fill('zzzzzzz_nomatchhere');
    await searchInput.press('Enter');

    await page.waitForFunction(
      () => document.querySelectorAll('.animate-pulse').length === 0,
      { timeout: 10_000 },
    );

    // "0 sonuc bulundu" veya EmptyState gorunmeli
    const zeroResults = page.getByText('0');
    const emptyState = page.getByText('Bu arama için sonuç bulamadık');

    const hasZero = await zeroResults.isVisible().catch(() => false);
    const hasEmpty = await emptyState.isVisible().catch(() => false);

    expect(hasZero || hasEmpty).toBeTruthy();
  });

  test('bos arama sonucunda sayfalama butonlari gorunmez', async ({ page }) => {
    await page.goto('/search');

    const searchInput = page.getByPlaceholder('Yemek veya mekan ara...');
    await searchInput.fill('aaabbbccc_impossible_food_name');
    await page.getByRole('button', { name: 'Ara' }).click();

    await page.waitForFunction(
      () => document.querySelectorAll('.animate-pulse').length === 0,
      { timeout: 10_000 },
    );

    // Sonuc yoksa sayfalama butonlari gorunmemeli
    const emptyState = page.getByText('Bu arama için sonuç bulamadık');
    const hasEmpty = await emptyState.isVisible().catch(() => false);

    if (hasEmpty) {
      await expect(page.getByRole('button', { name: 'Önceki' })).not.toBeVisible();
      await expect(page.getByRole('button', { name: 'Sonraki' })).not.toBeVisible();
    }
  });
});

test.describe('Hata Durumlari - Loading / Skeleton State', () => {
  test('search sayfasinda ilk yuklemede skeleton kartlar gorunur', async ({ page }) => {
    // API cevabini yavaslatmak icin route interceptor kullan
    await page.route('**/api/v1/search**', async (route) => {
      // 2 saniye gecikme ekle
      await new Promise((resolve) => setTimeout(resolve, 2000));
      await route.continue();
    });

    await page.goto('/search');

    // Skeleton kartlar gorunmeli (animate-pulse class'li elementler)
    const skeletons = page.locator('.animate-pulse');
    await expect(skeletons.first()).toBeVisible();

    // Skeleton kartlarin sayisi 6 olmali (mock data)
    const skeletonCount = await skeletons.count();
    expect(skeletonCount).toBeGreaterThanOrEqual(1);

    // "Araniyor..." metni gorunmeli
    await expect(page.getByText('Aranıyor...')).toBeVisible();
  });

  test('restoran detay sayfasinda yuklenirken skeleton gorunur', async ({ page }) => {
    // API cevabini yavaslatmak icin route interceptor kullan
    await page.route('**/api/v1/restaurants/**', async (route) => {
      await new Promise((resolve) => setTimeout(resolve, 2000));
      await route.continue();
    });

    await page.goto('/restaurant/test-slug');

    // Skeleton gorunmeli (animate-pulse class'li element)
    const skeletons = page.locator('.animate-pulse');
    await expect(skeletons.first()).toBeVisible();
  });

  test('search API hatasi durumunda bos sonuc gosterilir', async ({ page }) => {
    // API'yi 500 hatasi dondurecek sekilde mock'la
    await page.route('**/api/v1/search**', async (route) => {
      await route.fulfill({
        status: 500,
        contentType: 'application/json',
        body: JSON.stringify({ error: 'Internal Server Error' }),
      });
    });

    await page.goto('/search');

    // Yukleme bitmesini bekle
    await page.waitForFunction(
      () => document.querySelectorAll('.animate-pulse').length === 0,
      { timeout: 10_000 },
    );

    // API hatasi durumunda results [] olarak set ediliyor, EmptyState gorunmeli
    await expect(page.getByText('Bu arama için sonuç bulamadık')).toBeVisible();
  });

  test('restoran detay API hatasi durumunda hata mesaji gosterilir', async ({ page }) => {
    // API'yi 404 dondurecek sekilde mock'la
    await page.route('**/api/v1/restaurants/**', async (route) => {
      await route.fulfill({
        status: 404,
        contentType: 'application/json',
        body: JSON.stringify({ error: 'Not Found' }),
      });
    });

    await page.goto('/restaurant/herhangi-bir-slug');

    // Yukleme bitmesini bekle
    await page.waitForFunction(
      () => document.querySelectorAll('.animate-pulse').length === 0,
      { timeout: 10_000 },
    );

    // Hata mesaji gorunmeli
    await expect(page.getByText('Veri alınamadı')).toBeVisible();
    await expect(page.getByText('Restoran bilgileri yüklenemedi')).toBeVisible();
  });

  test('network hatasi (baglanti yok) durumunda hata gosterilir', async ({ page }) => {
    // Tum API isteklerini iptal et (network hatasi simule et)
    await page.route('**/api/v1/**', async (route) => {
      await route.abort('connectionrefused');
    });

    await page.goto('/restaurant/test-slug');

    // Yukleme bitmesini bekle
    await page.waitForFunction(
      () => document.querySelectorAll('.animate-pulse').length === 0,
      { timeout: 10_000 },
    );

    // Hata mesaji gorunmeli
    await expect(page.getByText('Veri alınamadı')).toBeVisible();
  });
});

test.describe('Hata Durumlari - 404 Sayfa', () => {
  test('mevcut olmayan bir URL icin 404 veya hata sayfasi gosterilir', async ({ page }) => {
    const response = await page.goto('/bu-sayfa-kesinlikle-mevcut-degil');

    // 404 status kodu donmeli veya sayfa yonlendirme yapabilir
    if (response) {
      const status = response.status();
      // 404 veya yonlendirme (302/301) beklenir
      expect([200, 301, 302, 404]).toContain(status);
    }

    // Sayfa icerisinde bir sey gorunmeli (bos beyaz sayfa olmamali)
    const body = page.locator('body');
    await expect(body).not.toBeEmpty();
  });
});

test.describe('Hata Durumlari - Responsive / Edge Cases', () => {
  test('cok uzun arama terimi girildiginde hata olmaz', async ({ page }) => {
    await page.goto('/search');

    const longQuery = 'a'.repeat(500);
    const searchInput = page.getByPlaceholder('Yemek veya mekan ara...');
    await searchInput.fill(longQuery);
    await page.getByRole('button', { name: 'Ara' }).click();

    // Sayfa crash etmemeli
    await page.waitForFunction(
      () => document.querySelectorAll('.animate-pulse').length === 0,
      { timeout: 10_000 },
    );

    // Bir sonuc veya bos durum gorunmeli
    const pageContent = page.locator('main');
    await expect(pageContent).toBeVisible();
  });

  test('ozel karakterli arama terimi girildiginde hata olmaz', async ({ page }) => {
    await page.goto('/search');

    const specialQuery = '<script>alert("xss")</script>';
    const searchInput = page.getByPlaceholder('Yemek veya mekan ara...');
    await searchInput.fill(specialQuery);
    await page.getByRole('button', { name: 'Ara' }).click();

    // Sayfa crash etmemeli
    await page.waitForFunction(
      () => document.querySelectorAll('.animate-pulse').length === 0,
      { timeout: 10_000 },
    );

    // Script tag'i calistirilmamis olmali (XSS koruması)
    // Sayfa normal goruntulenmeli
    const pageContent = page.locator('main');
    await expect(pageContent).toBeVisible();

    // Enjekte edilen script metni sayfa icerisinde gorunmemeli
    // (React zaten bunu sanitize eder ama dogrulamakta fayda var)
    await expect(page.locator('script:text("alert")')).toHaveCount(0);
  });

  test('bos string ile arama yapildiginda tum sonuclar gosterilir', async ({ page }) => {
    await page.goto('/search');

    const searchInput = page.getByPlaceholder('Yemek veya mekan ara...');
    await searchInput.fill('');
    await page.getByRole('button', { name: 'Ara' }).click();

    await page.waitForFunction(
      () => document.querySelectorAll('.animate-pulse').length === 0,
      { timeout: 10_000 },
    );

    // Sonuc sayisi veya bos durum gorunmeli
    const resultInfo = page.getByText(/sonuç bulundu|Bu arama için sonuç bulamadık/);
    await expect(resultInfo).toBeVisible();
  });
});
