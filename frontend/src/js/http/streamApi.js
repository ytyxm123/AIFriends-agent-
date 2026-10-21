/*
 * 功能：在每个请求头里自动添加`access token`。
 * 然后拦截请求结果，如果返回结果是身份认证失败（401），
 * 则说明`access_token`过期了，那么调用api刷新token`，
 * 如果刷新成功，则重新发送原请求。
*/
import { fetchEventSource } from '@microsoft/fetch-event-source';
import { useUserStore } from "@/stores/user.js";
import CONFIG_API from "@/js/config/config.js";

const BASE_URL = CONFIG_API.HTTP_URL

/**
 * 通用的流式请求工具
 * @param {string} url 请求地址
 * @param {object} options 配置项 (method, body, onmessage, onerror等)
 */
export default async function streamApi(url, options = {}) {
    const userStore = useUserStore();
    let refreshed = false;

    const startFetch = async () => {
        const controller = new AbortController();
        let refreshNeeded = false;
        let completed = false;
        await fetchEventSource(BASE_URL + url, {
            signal: controller.signal,
            credentials: 'include',
            method: options.method || 'POST',
            headers: {
                'Content-Type': 'application/json',
                'Accept': 'text/event-stream, application/json',
                'Authorization': `Bearer ${userStore.accessToken}`,
                ...options.headers,
            },
            body: JSON.stringify(options.body || {}),

            openWhenHidden: true,  // 允许后台运行，防止浏览器因隐藏页面而强制关闭它
            async onopen(response) {
                // 1. 处理 401 Token 过期
                if (response.status === 401) {
                    if (refreshed) {
                        userStore.logout();
                        throw new Error('登录已过期，请重新登录。');
                    }
                    refreshNeeded = true;
                    controller.abort();
                    return;
                }

                if (!response.ok || !response.headers.get('content-type')?.includes('text/event-stream')) {
                    const errorData = await response.json().catch(() => ({}));
                    throw new Error(errorData.detail || `请求失败: ${response.status}`);
                }
            },

            onmessage(msg) {
                if (msg.data === '[DONE]') {
                    completed = true;
                    if (options.onmessage) options.onmessage('', true);
                    controller.abort();
                    return
                }
                try {
                    const json = JSON.parse(msg.data);
                    if (options.onmessage) options.onmessage(json, false);
                } catch (e) {
                    console.error("流解析失败:", e);
                }
            },

            onerror(err) {
                throw err; // 停止自动重试
            },

            onclose() {
                if (!completed) throw new Error('回复连接中断，请重新发送。');
                options.onclose?.();
            },
        });
        if (refreshNeeded) {
            refreshed = true;
            const response = await fetch(BASE_URL + '/api/user/refresh/', {
                method: 'POST',
                credentials: 'include',
                headers: {'Content-Type': 'application/json'},
                body: '{}',
            });
            const data = await response.json();
            if (!response.ok || !data.access) {
                userStore.logout();
                throw new Error('登录已过期，请重新登录。');
            }
            userStore.setAccessToken(data.access);
            return startFetch();
        }
    };

    try {
        return await startFetch();
    } catch (error) {
        options.onerror?.(error);
        throw error;
    }
}
