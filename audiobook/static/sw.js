const CACHE_NAME = 'audiobook-app-v28';

const APP_SHELL = [
    '/',
    '/index.html',
    '/manifest.webmanifest'
];

self.addEventListener('install', (e) => {
    self.skipWaiting();
    e.waitUntil(
        caches.open(CACHE_NAME).then((cache) => {
            return Promise.all(APP_SHELL.map(url => {
                return fetch(url + '?v=' + Date.now()).then(response => {
                    if (!response.ok) throw new Error('Fetch failed');
                    return cache.put(url, response);
                });
            }));
        })
    );
});

self.addEventListener('activate', (e) => {
    e.waitUntil(
        caches.keys().then((keyList) => {
            return Promise.all(keyList.map((key) => {
                if (key !== CACHE_NAME && !key.startsWith('audiobook-media-user-')) {
                    return caches.delete(key);
                }
            }));
        }).then(() => self.clients.claim())
    );
});

// HTTP 206 Partial Content handler for offline MP3 seeking
async function handleRangeRequest(request, response) {
    const rangeHeader = request.headers.get('Range');
    if (!rangeHeader) return response; // Not a range request

    const buffer = await response.arrayBuffer();
    const total = buffer.byteLength;
    
    const parts = rangeHeader.replace(/bytes=/, "").split("-");
    const partialstart = parts[0];
    const partialend = parts[1];

    const start = parseInt(partialstart, 10);
    const end = partialend ? parseInt(partialend, 10) : total - 1;

    const chunksize = (end - start) + 1;
    const sliced = buffer.slice(start, end + 1);

    return new Response(sliced, {
        status: 206,
        statusText: 'Partial Content',
        headers: {
            'Content-Range': `bytes ${start}-${end}/${total}`,
            'Accept-Ranges': 'bytes',
            'Content-Length': chunksize,
            'Content-Type': response.headers.get('Content-Type') || 'audio/mpeg'
        }
    });
}

self.addEventListener('fetch', (e) => {
    const url = new URL(e.request.url);

    if (e.request.mode === 'navigate') {
        e.respondWith((async () => {
            const cache = await caches.open(CACHE_NAME);
            try {
                const response = await fetch(e.request);
                if (response.ok) {
                    await cache.put('/', response.clone());
                }
                return response;
            } catch (err) {
                return (await cache.match('/')) || (await cache.match('/index.html')) || Response.error();
            }
        })());
        return;
    }
    
    // Protected media caches
    if (url.pathname.startsWith('/api/books/') && (url.pathname.includes('/audio/') || url.pathname.includes('/cues/'))) {
        e.respondWith((async () => {
            const activeUser = url.searchParams.get('u');
            if (activeUser) {
                const userCacheName = `audiobook-media-user-${activeUser}`;
                const cache = await caches.open(userCacheName);
                
                // We cache it using the exact pathname to avoid query param mismatches
                const cachedResponse = await cache.match(url.pathname);
                
                if (cachedResponse) {
                    if (url.pathname.includes('/audio/')) {
                        return handleRangeRequest(e.request, cachedResponse);
                    }
                    return cachedResponse;
                }
            }
            
            return fetch(e.request);
        })());
        return;
    }
    
    if (url.pathname.startsWith('/api/')) {
        return; 
    }
    
    e.respondWith(
        caches.match(e.request).then((r) => {
            return r || fetch(e.request).then((response) => {
                return caches.open(CACHE_NAME).then((cache) => {
                    cache.put(e.request, response.clone());
                    return response;
                });
            });
        })
    );
});
