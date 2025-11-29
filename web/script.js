// 地图和标记
let map = null;
let markers = [];
let currentLocationMarker = null; // 当前位置标记
let isFirstLoad = true; // 是否是首次加载数据

// 当前选中的校区 campus（空字符串表示全部），默认选择玉泉校区
let currentCampus = "2143";

// 当前选中的服务商（空字符串表示全部）
let currentProvider = "";

// 可用服务商列表
let availableProviders = [];

// 关注列表（devid 和 devdescript 集合）
// 数据结构：{ devids: [{devid: number, provider: string}], devdescripts: [string] }
let watchlistDevids = new Set();
let watchlistDevdescripts = new Set();

// localStorage 键名
const WATCHLIST_STORAGE_KEY = 'zju_charger_watchlist';
const THEME_STORAGE_KEY = 'zju_charger_theme';

// 校区配置
// 注意：坐标格式为 [经度, 纬度] (lng, lat)
const CAMPUS_CONFIG = {
    2143: { name: "玉泉校区", center: [120.129265, 30.269646] }, // 教三位置
    1774: { name: "紫金港校区", center: [120.07707846383452,30.30430871105789] }
};

// 默认中心点：玉泉校区教三（BD-09 坐标，会自动转换为 GCJ-02）
const DEFAULT_CENTER = [120.129265, 30.269646];
const DEFAULT_ZOOM = 17; // 放大级别，便于查看充电桩位置

// 地图配置
const MAP_CONFIG = {
    dataCoordSystem: 'BD09',  // 数据源坐标系：'WGS84'、'GCJ02' 或 'BD09'
    webCoordSystem: 'GCJ02',  // 当前地图使用的坐标系：'WGS84'、'GCJ02' 或 'BD09'
    useMap: 'gaode'           // 当前使用的地图后端：'osm'、'gaode' 或 'baidu'
};

// 地图后端配置
const MAP_PROVIDERS = {
    osm: {
        name: 'OpenStreetMap',
        coordSystem: 'WGS84',
        tileLayer: 'https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png',
        options: {
            attribution: '© OpenStreetMap contributors',
            maxZoom: 19
        }
    },
    gaode: {
        name: '高德地图',
        coordSystem: 'GCJ02',
        tileLayer: 'http://webrd0{s}.is.autonavi.com/appmaptile?lang=zh_cn&size=1&scale=1&style=8&x={x}&y={y}&z={z}',
        options: {
            subdomains: ['1', '2', '3', '4'],
            minZoom: 1, // Leaflet 允许的最小缩放级别
            minNativeZoom: 3, // 高德地图实际支持的最小缩放级别，小于此级别时使用3级瓦片缩小显示
            maxZoom: 19, // Leaflet 允许的最大缩放级别
            maxNativeZoom: 18, // 高德地图实际支持的最大缩放级别，超过此级别时使用18级瓦片放大显示
            attribution: '© 高德地图'
        }
    },
    baidu: {
        name: '百度地图',
        coordSystem: 'BD09',
        tileLayer: 'http://api{s}.map.bdimg.com/customimage/tile?&x={x}&y={y}&z={z}&udt=20160928&scale=1',
        options: {
            subdomains: ['0', '1', '2'],
            minZoom: 3,
            maxZoom: 19,
            attribution: '© 百度地图'
        }
    }
};

// 坐标转换辅助函数
// 将数据源坐标系转换为地图使用的坐标系
function convertCoord(lat, lon) {
    const fromCoord = MAP_CONFIG.dataCoordSystem;
    const toCoord = MAP_CONFIG.webCoordSystem;
    
    // 如果坐标系相同，无需转换
    if (fromCoord === toCoord) {
        return [lat, lon];
    }
    
    // 定义转换函数映射表
    const convertFunctions = {
        'BD09->GCJ02': (lng, lat) => {
            if (typeof bd09ToGcj02 === 'function') {
                return bd09ToGcj02(lng, lat);
            }
            return [lng, lat];
        },
        'BD09->WGS84': (lng, lat) => {
            if (typeof bd09ToWgs84 === 'function') {
                return bd09ToWgs84(lng, lat);
            }
            return [lng, lat];
        },
        'GCJ02->BD09': (lng, lat) => {
            if (typeof gcj02ToBd09 === 'function') {
                return gcj02ToBd09(lng, lat);
            }
            return [lng, lat];
        },
        'GCJ02->WGS84': (lng, lat) => {
            if (typeof gcj02ToWgs84 === 'function') {
                return gcj02ToWgs84(lng, lat);
            }
            return [lng, lat];
        },
        'WGS84->BD09': (lng, lat) => {
            if (typeof wgs84ToBd09 === 'function') {
                return wgs84ToBd09(lng, lat);
            }
            return [lng, lat];
        },
        'WGS84->GCJ02': (lng, lat) => {
            if (typeof wgs84ToGcj02 === 'function') {
                return wgs84ToGcj02(lng, lat);
            }
            return [lng, lat];
        }
    };
    
    // 构建转换键
    const convertKey = `${fromCoord}->${toCoord}`;
    const convertFunc = convertFunctions[convertKey];
    
    if (convertFunc) {
        const result = convertFunc(lon, lat);
        return [result[1], result[0]]; // 返回 [lat, lng]
    }
    
    // 如果找不到转换函数，返回原坐标
    console.warn(`未找到坐标转换函数: ${convertKey}`);
    return [lat, lon];
}

// 当前地图图层
let currentTileLayer = null;

// 打印/下载插件实例
let printer = null;

// 初始化地图
function initMap() {
    // 如果地图已存在，先移除
    if (map) {
        map.remove();
    }
    
    // 根据当前选择的校区确定地图中心点
    let centerCoord = DEFAULT_CENTER;
    if (currentCampus && CAMPUS_CONFIG[currentCampus]) {
        centerCoord = CAMPUS_CONFIG[currentCampus].center;
    }
    
    // 转换中心点坐标
    const center = convertCoord(centerCoord[0], centerCoord[1]);
    
    // 创建地图实例
    map = L.map('map').setView(center, DEFAULT_ZOOM);
    
    // 添加当前配置的地图图层（这会设置 currentTileLayer）
    switchMap(MAP_CONFIG.useMap);
    
    // 初始化下载地图插件（隐藏默认控件，使用自定义按钮）
    // 注意：必须在 switchMap 之后初始化，因为需要 currentTileLayer
    if (typeof L.easyPrint !== 'undefined' && currentTileLayer) {
        printer = L.easyPrint({
            tileLayer: currentTileLayer,
            exportOnly: true,
            filename: 'ZJU-Charger-Map',
            sizeModes: ['Current'],
            hidden: true,  // 隐藏默认控件
            hideControlContainer: true
        }).addTo(map);
    }
}

function manualPrint() {
    if (!map) {
        console.error('地图未初始化');
        alert('地图未初始化，无法下载');
        return;
    }
    
    if (!printer) {
        // 尝试重新初始化打印机
        if (typeof L.easyPrint !== 'undefined' && currentTileLayer) {
            printer = L.easyPrint({
                tileLayer: currentTileLayer,
                exportOnly: true,
                filename: 'ZJU-Charger-Map',
                sizeModes: ['Current'],
                hidden: true,
                hideControlContainer: true
            }).addTo(map);
        } else {
            console.error('下载插件不可用');
            alert('下载功能不可用，请检查地图是否已加载');
            return;
        }
    }
    
    try {
        const filename = 'ZJU-Charger-Map-' + new Date().toISOString().replace(/[:.]/g, '-').slice(0, -5);
        printer.printMap('CurrentSize', filename);
    } catch (error) {
        console.error('下载地图失败:', error);
        alert('下载失败: ' + (error.message || '未知错误'));
    }
}

// 切换地图后端
function switchMap(mapProvider) {
    if (!map) {
        console.error('地图未初始化');
        return;
    }
    
    // 验证地图提供商
    if (!MAP_PROVIDERS[mapProvider]) {
        console.error(`未知的地图提供商: ${mapProvider}`);
        return;
    }
    
    // 移除旧图层
    if (currentTileLayer) {
        map.removeLayer(currentTileLayer);
    }
    
    // 如果当前位置标记存在，需要重新转换坐标
    if (currentLocationMarker) {
        const latlng = currentLocationMarker.getLatLng();
        // 获取原始 WGS84 坐标（如果之前保存了）
        // 这里简化处理：移除旧标记，用户需要重新定位
        map.removeLayer(currentLocationMarker);
        currentLocationMarker = null;
    }
    
    // 更新配置
    MAP_CONFIG.useMap = mapProvider;
    const provider = MAP_PROVIDERS[mapProvider];
    MAP_CONFIG.webCoordSystem = provider.coordSystem;
    
    // 创建新图层
    currentTileLayer = L.tileLayer(provider.tileLayer, provider.options);
    currentTileLayer.addTo(map);
    
    // 重新初始化下载地图插件（因为图层已更换）
    if (printer) {
        map.removeControl(printer);
        printer = null;
    }
    if (typeof L.easyPrint !== 'undefined' && currentTileLayer) {
        printer = L.easyPrint({
            tileLayer: currentTileLayer,
            exportOnly: true,
            filename: 'ZJU-Charger-Map',
            sizeModes: ['Current'],
            hidden: true,  // 隐藏默认控件
            hideControlContainer: true
        }).addTo(map);
    }
    
    // 更新选择器状态
    updateMapSelector();
    
    // 重新转换并设置中心点（保持当前缩放级别）
    const center = convertCoord(DEFAULT_CENTER[0], DEFAULT_CENTER[1]);
    map.setView(center, map.getZoom());
    
    // 重新渲染所有标记（因为坐标系改变了）
    // 切换地图服务时保持当前位置（false），因为用户可能已经定位到某个位置
    if (window.currentStations && window.currentStations.length > 0) {
        // 合并所有站点用于地图显示（包括未抓取的）
        const allStationsForMap = [...(window.currentStations || [])];
        if (window.allStationsDef && window.allStationsDef.length > 0) {
            const fetchedNames = new Set((window.currentStations || []).map(s => s.name));
            window.allStationsDef.forEach(def => {
                const devdescript = def.devdescript || def.name;
                if (!fetchedNames.has(devdescript)) {
                    const matchesProvider = !currentProvider || def.provider_id === currentProvider;
                    if (matchesProvider) {
                        allStationsForMap.push({
                            name: devdescript,
                            free: 0,
                            total: 0,
                            used: 0,
                            error: 0,
                            devids: def.devid ? [def.devid] : [],
                            provider_id: def.provider_id || 'unknown',
                            provider_name: def.provider_name || '未知',
                            campus: def.areaid,
                            lat: def.latitude,
                            lon: def.longitude,
                            isFetched: false
                        });
                    }
                }
            });
        }
        renderMap(allStationsForMap, false); // 切换地图服务时保持当前位置
    }
    
    console.log(`已切换到: ${provider.name} (${provider.coordSystem})`);
}

// 更新地图选择器状态
function updateMapSelector() {
    const selector = document.getElementById('map-selector');
    if (selector) {
        selector.value = MAP_CONFIG.useMap;
    }
}

// 从 localStorage 加载关注列表
function loadWatchlistFromStorage() {
    try {
        const stored = localStorage.getItem(WATCHLIST_STORAGE_KEY);
        if (stored) {
            const data = JSON.parse(stored);
            // 将 devid 列表转换为 Set（使用字符串键 "devid:provider" 来唯一标识）
            watchlistDevids.clear();
            if (data.devids && Array.isArray(data.devids)) {
                data.devids.forEach(item => {
                    if (item.devid && item.provider) {
                        watchlistDevids.add(`${item.devid}:${item.provider}`);
                    }
                });
            }
            // 将 devdescript 列表转换为 Set
            watchlistDevdescripts = new Set(data.devdescripts || []);
            return true;
        }
    } catch (error) {
        console.error('加载关注列表失败:', error);
    }
    // 如果加载失败或不存在，初始化为空
    watchlistDevids.clear();
    watchlistDevdescripts.clear();
    return false;
}

// 保存关注列表到 localStorage
function saveWatchlistToStorage() {
    try {
        // 将 Set 转换为数组格式
        const devidsArray = [];
        watchlistDevids.forEach(key => {
            const [devid, provider] = key.split(':');
            if (devid && provider) {
                devidsArray.push({ devid: parseInt(devid), provider: provider });
            }
        });
        
        const data = {
            devids: devidsArray,
            devdescripts: Array.from(watchlistDevdescripts),
            updated_at: new Date().toISOString()
        };
        localStorage.setItem(WATCHLIST_STORAGE_KEY, JSON.stringify(data));
        return true;
    } catch (error) {
        console.error('保存关注列表失败:', error);
        return false;
    }
}

// 获取关注列表（从 localStorage 读取）
function fetchWatchlist() {
    return loadWatchlistFromStorage();
}

// 检查是否已关注
function isWatched(devids, devdescript, providerId) {
    // 检查 devid（需要同时匹配 devid 和 provider）
    if (devids && devids.length > 0 && providerId) {
        const hasDevid = devids.some(devid => {
            const key = `${parseInt(devid)}:${providerId}`;
            return watchlistDevids.has(key);
        });
        if (hasDevid) return true;
    }
    // 检查 devdescript
    if (devdescript && watchlistDevdescripts.has(devdescript)) {
        return true;
    }
    return false;
}

// 切换关注状态（直接操作 localStorage）
async function toggleWatchlist(devids, devdescript, providerId) {
    // 如果没有 devids 和 devdescript，无法操作
    if ((!devids || devids.length === 0) && !devdescript) {
        console.error('切换关注状态失败: 缺少 devids 或 devdescript');
        alert('操作失败: 缺少站点信息');
        return false;
    }
    
    // 如果有 devids 但没有 providerId，尝试从当前站点数据中查找
    if (devids && devids.length > 0 && !providerId) {
        // 尝试从当前站点数据中查找 providerId
        if (window.currentStations && devdescript) {
            const station = window.currentStations.find(s => s.name === devdescript);
            if (station && station.provider_id) {
                providerId = station.provider_id;
            }
        }
        
        // 如果仍然没有找到 providerId，只使用 devdescript
        if (!providerId) {
            console.warn('无法获取 providerId，将只使用 devdescript 进行关注');
            // 继续执行，只使用 devdescript
        }
    }
    
    const currentlyWatched = isWatched(devids, devdescript, providerId);
    
    try {
        if (currentlyWatched) {
            // 移除关注
            if (devids && devids.length > 0 && providerId) {
                devids.forEach(devid => {
                    const key = `${parseInt(devid)}:${providerId}`;
                    watchlistDevids.delete(key);
                });
            }
            if (devdescript) {
                watchlistDevdescripts.delete(devdescript);
            }
        } else {
            // 添加关注
            if (devids && devids.length > 0 && providerId) {
                devids.forEach(devid => {
                    const key = `${parseInt(devid)}:${providerId}`;
                    watchlistDevids.add(key);
                });
            }
            if (devdescript) {
                watchlistDevdescripts.add(devdescript);
            }
        }
        
        // 保存到 localStorage
        saveWatchlistToStorage();
        
        // 重新渲染列表以更新收藏状态
        if (window.currentStations) {
            renderList(window.currentStations, window.allStationsDef);
        }
        return true;
    } catch (error) {
        console.error('切换关注状态失败:', error);
        alert(`操作失败: ${error.message || '未知错误'}`);
        return false;
    }
}

// 获取关注列表站点状态（通过 devid+provider 查询 API）
async function fetchWatchlistStatus() {
    try {
        // 从 localStorage 读取 watchlist
        loadWatchlistFromStorage();
        
        // 按 provider 分组 devid
        const providerDevidsMap = new Map();
        watchlistDevids.forEach(key => {
            const [devid, provider] = key.split(':');
            if (devid && provider) {
                if (!providerDevidsMap.has(provider)) {
                    providerDevidsMap.set(provider, []);
                }
                providerDevidsMap.get(provider).push(parseInt(devid));
            }
        });
        
        // 如果没有 devid，返回空结果
        if (providerDevidsMap.size === 0 && watchlistDevdescripts.size === 0) {
            return {
                updated_at: new Date().toISOString(),
                stations: []
            };
        }
        
        // 对每个 provider，调用 API 获取关注站点状态
        const allStations = [];
        const promises = [];
        
        for (const [provider, devids] of providerDevidsMap.entries()) {
            // 构建 API URL
            let apiUrl = `/api/status?provider=${encodeURIComponent(provider)}`;
            devids.forEach(devid => {
                apiUrl += `&devid=${devid}`;
            });
            
            // 发起请求
            promises.push(
                fetch(apiUrl)
                    .then(response => {
                        if (response.ok) {
                            return response.json();
                        }
                        throw new Error(`API 返回错误: ${response.status}`);
                    })
                    .then(data => {
                        if (data && data.stations) {
                            allStations.push(...data.stations);
                        }
                    })
                    .catch(error => {
                        console.error(`获取 ${provider} 的关注站点状态失败:`, error);
                    })
            );
        }
        
        // 等待所有请求完成
        await Promise.all(promises);
        
        // 如果还有 devdescript，需要从所有站点中过滤
        if (watchlistDevdescripts.size > 0) {
            // 获取所有站点数据
            try {
                const allStationsResponse = await fetch('/api/status');
                if (allStationsResponse.ok) {
                    const allData = await allStationsResponse.json();
                    if (allData && allData.stations) {
                        // 过滤出匹配的站点
                        const matchedStations = allData.stations.filter(station => {
                            return watchlistDevdescripts.has(station.name);
                        });
                        // 合并到结果中（去重）
                        const existingNames = new Set(allStations.map(s => s.name));
                        matchedStations.forEach(station => {
                            if (!existingNames.has(station.name)) {
                                allStations.push(station);
                            }
                        });
                    }
                }
            } catch (error) {
                console.error('获取所有站点数据失败:', error);
            }
        }
        
        return {
            updated_at: new Date().toISOString(),
            stations: allStations
        };
    } catch (error) {
        console.error('获取关注列表状态失败:', error);
        return {
            updated_at: new Date().toISOString(),
            stations: []
        };
    }
}

// 显示限流弹窗提醒
function showRateLimitAlert() {
    // 检查是否已经存在弹窗
    let alertEl = document.getElementById('rate-limit-alert');
    if (alertEl) {
        // 如果已存在，先移除
        alertEl.remove();
    }
    
    // 创建弹窗元素
    alertEl = document.createElement('div');
    alertEl.id = 'rate-limit-alert';
    alertEl.className = 'fixed top-4 right-4 z-50 max-w-sm w-full';
    alertEl.innerHTML = `
        <div class="bg-yellow-50 dark:bg-yellow-900/20 border border-yellow-200 dark:border-yellow-800 text-yellow-800 dark:text-yellow-300 p-4 rounded-lg shadow-lg">
            <div class="flex items-start gap-3">
                <svg class="w-5 h-5 mt-0.5 flex-shrink-0" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                    <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M12 9v2m0 4h.01m-6.938 4h13.856c1.54 0 2.502-1.667 1.732-3L13.732 4c-.77-1.333-2.694-1.333-3.464 0L3.34 16c-.77 1.333.192 3 1.732 3z"></path>
                </svg>
                <div class="flex-1">
                    <p class="font-medium">请求过于频繁</p>
                    <p class="text-sm mt-1">请稍后再试，避免频繁刷新页面</p>
                </div>
                <button onclick="this.closest('#rate-limit-alert').remove()" class="text-yellow-600 dark:text-yellow-400 hover:text-yellow-800 dark:hover:text-yellow-200">
                    <svg class="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                        <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M6 18L18 6M6 6l12 12"></path>
                    </svg>
                </button>
            </div>
        </div>
    `;
    
    // 添加到页面
    document.body.appendChild(alertEl);
    
    // 3秒后自动消失
    setTimeout(() => {
        if (alertEl && alertEl.parentNode) {
            alertEl.style.transition = 'opacity 0.3s ease-out';
            alertEl.style.opacity = '0';
            setTimeout(() => {
                if (alertEl && alertEl.parentNode) {
                    alertEl.remove();
                }
            }, 300);
        }
    }, 3000);
}

// 加载可用服务商列表
async function loadProviders() {
    try {
        const response = await fetch('/api/providers');
        if (response.status === 429) {
            // 限流错误
            showRateLimitAlert();
            return false;
        }
        if (response.ok) {
            const providers = await response.json();
            availableProviders = providers;
            
            // 更新服务商选择器
            const selector = document.getElementById('provider-selector');
            if (selector) {
                // 保留"全部服务商"选项
                const allOption = selector.querySelector('option[value=""]');
                selector.innerHTML = '';
                if (allOption) {
                    selector.appendChild(allOption);
                }
                
                // 添加服务商选项
                providers.forEach(provider => {
                    const option = document.createElement('option');
                    option.value = provider.id;
                    option.textContent = provider.name;
                    selector.appendChild(option);
                });
            }
            return true;
        }
    } catch (error) {
        console.error('获取服务商列表失败:', error);
    }
    return false;
}

// 获取站点状态
async function fetchStatus() {
    const loadingEl = document.getElementById('loading');
    const listEl = document.getElementById('station-list');
    
    loadingEl.style.display = 'block';
    listEl.innerHTML = '';
    
    try {
        // 构建 API URL，支持 provider 参数
        let apiUrl = '/api/status';
        if (currentProvider) {
            apiUrl += `?provider=${encodeURIComponent(currentProvider)}`;
        }
        
        // 先尝试调用 API
        let data;
        try {
            const response = await fetch(apiUrl);
            if (response.status === 429) {
                // 限流错误
                showRateLimitAlert();
                throw new Error('请求过于频繁，请稍后再试');
            }
            if (response.ok) {
                data = await response.json();
            } else {
                throw new Error('API 调用失败');
            }
        } catch (error) {
            // Fallback 到静态文件
            console.log('API 调用失败，尝试加载缓存数据...', error);
            const response = await fetch('/data/latest.json');
            if (response.ok) {
                data = await response.json();
                // 如果选择了服务商，需要过滤数据
                if (currentProvider && data.stations) {
                    data.stations = data.stations.filter(s => s.provider_id === currentProvider);
                }
            } else {
                throw new Error('无法加载数据');
            }
        }
        
        // 加载所有站点定义（stations.json）
        let allStationsDef = [];
        try {
            const stationsResponse = await fetch('/data/stations.json');
            if (stationsResponse.ok) {
                const stationsData = await stationsResponse.json();
                allStationsDef = stationsData.stations || [];
            }
        } catch (error) {
            console.log('无法加载 stations.json，将只显示已抓取的站点', error);
        }
        
        if (data && data.stations) {
            if (data.stations.length === 0 && allStationsDef.length === 0) {
                // 数据为空，显示提示
                const listEl = document.getElementById('station-list');
                listEl.innerHTML = `
                    <div class="bg-red-50 dark:bg-red-900/20 border border-red-200 dark:border-red-800 text-red-800 dark:text-red-300 p-4 rounded-lg text-center">
                        <p class="font-medium">暂无站点数据</p>
                        <p class="text-sm mt-2">请确保服务器已成功抓取数据</p>
                        <p class="text-sm mt-1 text-red-600 dark:text-red-400">如果服务器正在运行，请检查控制台错误信息</p>
                    </div>
                `;
                updateTime(data.updated_at || '未知');
            } else {
                // 保存当前数据供校区切换使用
                window.currentStations = data.stations;
                window.allStationsDef = allStationsDef;
                
                // 合并所有站点用于地图显示
                const allStationsForMap = [...data.stations];
                if (allStationsDef && allStationsDef.length > 0) {
                    const fetchedNames = new Set(data.stations.map(s => s.name));
                    allStationsDef.forEach(def => {
                        const devdescript = def.devdescript || def.name;
                        if (!fetchedNames.has(devdescript)) {
                            const matchesProvider = !currentProvider || def.provider_id === currentProvider;
                            if (matchesProvider) {
                                allStationsForMap.push({
                                    name: devdescript,
                                    free: 0,
                                    total: 0,
                                    used: 0,
                                    error: 0,
                                    devids: def.devid ? [def.devid] : [],
                                    provider_id: def.provider_id || 'unknown',
                                    provider_name: def.provider_name || '未知',
                                    campus: def.areaid,
                                    lat: def.latitude,
                                    lon: def.longitude,
                                    isFetched: false
                                });
                            }
                        }
                    });
                }
                
                // 刷新数据时，只更新标记和列表，不重置地图视图
                // 传入 false 表示不允许自动调整地图视野，保持用户当前位置
                renderMap(allStationsForMap, false);
                renderList(data.stations, allStationsDef);
                updateTime(data.updated_at);
                
                // 标记首次加载完成
                if (isFirstLoad) {
                    isFirstLoad = false;
                }
            }
        } else {
            throw new Error('数据格式错误：缺少 stations 字段');
        }
    } catch (error) {
        console.error('获取数据失败:', error);
        listEl.innerHTML = `
            <div class="bg-red-50 dark:bg-red-900/20 border border-red-200 dark:border-red-800 text-red-800 dark:text-red-300 p-4 rounded-lg text-center">
                <p class="font-medium">加载数据失败</p>
                <p class="text-sm mt-2">${error.message}</p>
                <p class="text-sm mt-2 text-red-600 dark:text-red-400">
                    请检查：<br>
                    1. 服务器是否正在运行<br>
                    2. 网络连接是否正常<br>
                    3. 查看浏览器控制台获取详细错误信息
                </p>
            </div>
        `;
    } finally {
        loadingEl.style.display = 'none';
    }
}

// 过滤站点（按校区）
function filterStationsByCampus(stations) {
    if (!currentCampus) {
        return stations;  // 显示全部
    }
    const filtered = stations.filter(s => s.campus && s.campus.toString() === currentCampus);
    console.log(`[filterStationsByCampus] currentCampus=${currentCampus}, total=${stations.length}, filtered=${filtered.length}`);
    return filtered;
}

// 过滤站点（按服务商）
function filterStationsByProvider(stations) {
    if (!currentProvider) {
        return stations;  // 显示全部
    }
    return stations.filter(s => s.provider_id === currentProvider);
}

// 渲染地图
// allowFitBounds: 是否允许自动调整地图视野（true: 允许，false: 保持当前位置）
function renderMap(stations, allowFitBounds = false) {
    // 保存当前地图视图状态（中心点和缩放级别）
    const currentCenter = map.getCenter();
    const currentZoom = map.getZoom();
    
    // 清除现有标记（只清除充电桩标记，保留当前位置标记）
    markers.forEach(marker => map.removeLayer(marker));
    markers = [];
    
    // 按校区和服务商过滤
    let filteredStations = filterStationsByCampus(stations);
    filteredStations = filterStationsByProvider(filteredStations);
    
    // 服务商形状映射（用于区分不同服务商）
    const providerShapes = {
        'neptune': 'circle',  // 圆形
        // 可以添加更多服务商形状
        // 'provider2': 'triangle',  // 三角形
        // 'provider3': 'square',    // 正方形
    };
    
    // 创建不同形状的图标函数
    function createMarkerIcon(color, shape, number) {
        const size = 24;
        const borderWidth = 2;
        const borderColor = '#ffffff';
        const shadow = '0 2px 6px rgba(0,0,0,0.3)';
        
        let shapeStyle = '';
        let clipPath = '';
        
        switch(shape) {
            case 'triangle':
                // 三角形（使用clip-path）
                shapeStyle = `
                    width: ${size}px;
                    height: ${size}px;
                    background-color: ${color};
                    clip-path: polygon(50% 0%, 0% 100%, 100% 100%);
                    display: flex;
                    align-items: center;
                    justify-content: center;
                    padding-top: 2px;
                `;
                break;
            case 'square':
                // 正方形
                shapeStyle = `
                    width: ${size}px;
                    height: ${size}px;
                    background-color: ${color};
                    border-radius: 4px;
                    display: flex;
                    align-items: center;
                    justify-content: center;
                `;
                break;
            case 'circle':
            default:
                // 圆形（默认）
                shapeStyle = `
                    width: ${size}px;
                    height: ${size}px;
                    background-color: ${color};
                    border-radius: 50%;
                    display: flex;
                    align-items: center;
                    justify-content: center;
                `;
                break;
        }
        
        return `
            <div style="
                ${shapeStyle}
                border: ${borderWidth}px solid ${borderColor};
                color: white;
                font-weight: bold;
                font-size: 11px;
                box-shadow: ${shadow};
                position: relative;
            ">
                <span>${number}</span>
            </div>
        `;
    }
    
    // 显示所有站点（包括非空闲的和未抓取的）
    filteredStations.forEach(station => {
        const { name, lat, lon, free, total, provider_id, provider_name, isFetched } = station;
        
        // 如果没有坐标，跳过
        if (!lat || !lon) {
            return;
        }
        
        // 坐标转换
        const [markerLat, markerLon] = convertCoord(lat, lon);
        
        // 根据空闲数量选择颜色（统一的颜色方案）
        let color = '#10b981'; // 绿色：有空闲（更柔和的绿色）
        if (isFetched === false) {
            color = '#9ca3af'; // 灰色：未抓取到
        } else if (free === 0) {
            color = '#ef4444'; // 红色：无空闲
        } else if (free <= 2) {
            color = '#f59e0b'; // 橙色：少量空闲
        }
        
        // 获取服务商对应的形状
        const shape = providerShapes[provider_id] || 'circle';
        
        // 创建带数字的自定义图标（使用不同形状）
        const displayNumber = isFetched === false ? '?' : free;
        const iconHtml = createMarkerIcon(color, shape, displayNumber);
        
        const customIcon = L.divIcon({
            html: iconHtml,
            className: '',
            iconSize: [24, 24],
            iconAnchor: [12, 12]
        });
        
        // 创建标记
        const marker = L.marker([markerLat, markerLon], {
            icon: customIcon
        }).addTo(map);
        
        // 添加弹出窗口（显示服务商信息）
        if (isFetched === false) {
            marker.bindPopup(`
                <div style="text-align: center; min-width: 120px;">
                    <strong style="font-size: 14px;">${name}</strong><br>
                    <span style="font-size: 11px; color: #6b7280;">${provider_name || provider_id}</span><br>
                    <span style="font-size: 13px; margin-top: 4px; display: inline-block; color: #9ca3af;">
                        未抓取到数据
                    </span>
                </div>
            `);
        } else {
            const freeColor = free === 0 ? '#ef4444' : '#10b981';
            marker.bindPopup(`
                <div style="text-align: center; min-width: 120px;">
                    <strong style="font-size: 14px;">${name}</strong><br>
                    <span style="font-size: 11px; color: #6b7280;">${provider_name || provider_id}</span><br>
                    <span style="font-size: 13px; margin-top: 4px; display: inline-block;">
                        可用: <span style="color: ${freeColor}; font-weight: bold;">${free}</span> / ${total}
                    </span>
                </div>
            `);
        }
        
        markers.push(marker);
    });
    
    // 根据 allowFitBounds 参数决定是否调整地图视野
    if (allowFitBounds || isFirstLoad) {
        // 允许调整视野：首次加载或主动切换校区/服务商时
        if (markers.length > 0) {
            const group = new L.featureGroup(markers);
            map.fitBounds(group.getBounds().pad(0.1));
        } else if (currentCampus && CAMPUS_CONFIG[currentCampus]) {
            // 如果没有标记但选择了校区，定位到校区中心
            const campus = CAMPUS_CONFIG[currentCampus];
            const center = convertCoord(campus.center[0], campus.center[1]);
            map.setView(center, DEFAULT_ZOOM);
        }
        if (isFirstLoad) {
            isFirstLoad = false;
        }
    } else {
        // 不允许调整视野：数据刷新时保持用户当前的地图位置和缩放级别
        map.setView(currentCenter, currentZoom);
    }
}

// 渲染列表
function renderList(stations, allStationsDef = []) {
    const listEl = document.getElementById('station-list');
    
    // 创建已抓取站点的映射（使用 name 作为键）
    const fetchedStationsMap = new Map();
    stations.forEach(s => {
        fetchedStationsMap.set(s.name, s);
    });
    
    // 合并所有站点：已抓取的和未抓取的
    const allStations = [];
    
    // 添加已抓取的站点
    stations.forEach(s => {
        allStations.push({ ...s, isFetched: true });
    });
    
    // 添加未抓取的站点（从 stations.json）
    if (allStationsDef && allStationsDef.length > 0) {
        allStationsDef.forEach(def => {
            const devdescript = def.devdescript || def.name;
            // 如果这个站点没有被抓取到，添加为未抓取状态
            if (!fetchedStationsMap.has(devdescript)) {
                // 检查是否匹配当前过滤条件
                const matchesProvider = !currentProvider || def.provider_id === currentProvider;
                const matchesCampus = !currentCampus || (def.areaid && def.areaid.toString() === currentCampus);
                
                if (matchesProvider && matchesCampus) {
                    allStations.push({
                        name: devdescript,
                        free: 0,
                        total: 0,
                        used: 0,
                        error: 0,
                        devids: def.devid ? [def.devid] : [],
                        provider_id: def.provider_id || 'unknown',
                        provider_name: def.provider_name || '未知',
                        campus: def.areaid,
                        lat: def.latitude,
                        lon: def.longitude,
                        isFetched: false
                    });
                }
            }
        });
    }
    
    // 按校区和服务商过滤
    let filteredStations = filterStationsByCampus(allStations);
    filteredStations = filterStationsByProvider(filteredStations);
    
    // 排序逻辑：关注列表优先，然后按可用数量排序
    const sortedStations = [...filteredStations].sort((a, b) => {
        // 检查是否已关注
        const aWatched = isWatched(a.devids || [], a.name, a.provider_id);
        const bWatched = isWatched(b.devids || [], b.name, b.provider_id);
        
        // 如果一个是关注的，另一个不是，关注的排在前面
        if (aWatched !== bWatched) {
            return aWatched ? -1 : 1;
        }
        
        // 如果都是关注的或都不是关注的，继续其他排序规则
        // 已抓取的排在前面
        if (a.isFetched !== b.isFetched) {
            return a.isFetched ? -1 : 1;
        }
        
        // 按可用数量排序（从多到少）
        return b.free - a.free;
    });
    
    if (sortedStations.length === 0) {
        listEl.innerHTML = '<div class="bg-red-50 dark:bg-red-900/20 border border-red-200 dark:border-red-800 text-red-800 dark:text-red-300 p-4 rounded-lg text-center">暂无站点数据</div>';
        return;
    }
    
    listEl.innerHTML = sortedStations.map(station => {
        const { name, free, total, used, error, devids, provider_id, provider_name, campus, isFetched } = station;
        
        // 计算使用率
        const usagePercent = total > 0 ? (used / total) * 100 : 0;
        const freePercent = total > 0 ? (free / total) * 100 : 0;
        const errorPercent = total > 0 ? (error / total) * 100 : 0;
        
        // 可用部分统一使用绿色
        const barColor = '#10b981'; // 绿色：可用部分统一颜色
        
        // 检查是否没有可用充电桩
        const isUnavailable = free === 0;
        
        // 检查是否未抓取到
        const isNotFetched = isFetched === false;
        
        // 优化背景和边框配色（支持暗色模式）
        const itemBgClass = isNotFetched ? 'bg-gray-100 dark:bg-gray-700/50' : 'bg-white dark:bg-gray-800';
        const itemBorderClass = isNotFetched ? 'border-gray-300 dark:border-gray-600' : 'border-gray-200 dark:border-gray-700';
        const itemHoverBorderClass = isNotFetched ? '' : 'hover:border-blue-400 dark:hover:border-blue-500';
        const itemHoverBgClass = isNotFetched ? '' : 'hover:bg-blue-50 dark:hover:bg-blue-900/30';
        const cursorClass = isNotFetched ? 'cursor-not-allowed' : 'cursor-pointer';
        const grayscaleClass = isNotFetched ? 'grayscale opacity-60' : '';
        
        // 检查是否已关注
        const stationDevids = devids || [];
        const watched = isWatched(stationDevids, name, provider_id);
        
        // Heroicons 风格的星形图标（实心/空心）- 表示收藏/关注
        const starIcon = watched 
            ? `<svg class="w-5 h-5 text-yellow-500 dark:text-yellow-400" fill="currentColor" viewBox="0 0 20 20" xmlns="http://www.w3.org/2000/svg">
                <path d="M9.049 2.927c.3-.921 1.603-.921 1.902 0l1.07 3.292a1 1 0 00.95.69h3.462c.969 0 1.371 1.24.588 1.81l-2.8 2.034a1 1 0 00-.364 1.118l1.07 3.292c.3.921-.755 1.688-1.54 1.118l-2.8-2.034a1 1 0 00-1.175 0l-2.8 2.034c-.784.57-1.838-.197-1.539-1.118l1.07-3.292a1 1 0 00-.364-1.118L2.98 8.72c-.783-.57-.38-1.81.588-1.81h3.461a1 1 0 00.951-.69l1.07-3.292z"></path>
            </svg>`
            : `<svg class="w-5 h-5 text-gray-400 dark:text-gray-500 hover:text-yellow-500 dark:hover:text-yellow-400" fill="none" stroke="currentColor" viewBox="0 0 24 24" xmlns="http://www.w3.org/2000/svg">
                <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M11.049 2.927c.3-.921 1.603-.921 1.902 0l1.519 4.674a1 1 0 00.95.69h4.915c.969 0 1.371 1.24.588 1.81l-3.976 2.888a1 1 0 00-.363 1.118l1.518 4.674c.3.922-.755 1.688-1.538 1.118l-3.976-2.888a1 1 0 00-1.176 0l-3.976 2.888c-.783.57-1.838-.197-1.538-1.118l1.518-4.674a1 1 0 00-.363-1.118l-3.976-2.888c-.784-.57-.38-1.81.588-1.81h4.914a1 1 0 00.951-.69l1.519-4.674z"></path>
            </svg>`;
        
        // 将 devids 转换为 JSON 字符串以便在 data 属性中使用
        const devidsJson = JSON.stringify(stationDevids);
        
        // 获取校区名称
        const campusName = campus && CAMPUS_CONFIG[campus] ? CAMPUS_CONFIG[campus].name : '未知校区';
        
        // 服务商形状图标
        const providerShapesForBadge = {
            'neptune': '●',  // 圆形
            // 'provider2': '▲',  // 三角形
            // 'provider3': '■',  // 正方形
        };
        const shapeIcon = providerShapesForBadge[provider_id] || '●';
        
        // 站点名称截断（最多显示20个字符）
        const displayName = name.length > 20 ? name.substring(0, 20) + '...' : name;
        
        const titleText = isNotFetched ? '未抓取到数据' : name;
        
        return `
            <div class="p-4 border ${itemBorderClass} rounded-lg ${itemBgClass} transition-all duration-200 ${cursorClass} ${itemHoverBorderClass} ${itemHoverBgClass} ${grayscaleClass}" data-name="${name}" data-available="${!isNotFetched}" data-provider-id="${provider_id || ''}" title="${titleText}">
                <!-- 站点名称和关注按钮 -->
                <div class="flex justify-between items-start mb-3 gap-2">
                    <span class="font-semibold text-base ${isNotFetched ? 'text-gray-500 dark:text-gray-400' : 'text-gray-900 dark:text-gray-100'} truncate flex-1" title="${name}">${displayName}</span>
                    <span class="cursor-pointer select-none transition-transform duration-200 hover:scale-110 active:scale-95 flex-shrink-0 p-1 -mr-1 focus:outline-none focus:ring-2 focus:ring-yellow-500 dark:focus:ring-yellow-400 rounded" data-devids='${devidsJson}' data-devdescript="${name}" title="${watched ? '取消收藏' : '添加收藏'}">${starIcon}</span>
                </div>
                
                <!-- 颜色条：显示使用情况（可用部分在最左侧） -->
                <div class="mb-3">
                    ${isNotFetched ? `
                        <div class="h-3 bg-gray-300 dark:bg-gray-600 rounded-full"></div>
                        <div class="flex justify-between items-center mt-1 text-xs text-gray-400 dark:text-gray-500">
                            <span>未抓取到数据</span>
                        </div>
                    ` : `
                        <div class="h-3 bg-gray-200 dark:bg-gray-700 rounded-full overflow-hidden flex">
                            ${free > 0 ? `<div style="background-color: ${barColor}; width: ${freePercent}%"></div>` : ''}
                            ${used > 0 ? `<div class="bg-gray-400 dark:bg-gray-600" style="width: ${usagePercent}%"></div>` : ''}
                            ${error > 0 ? `<div class="bg-red-500 dark:bg-red-600" style="width: ${errorPercent}%"></div>` : ''}
                        </div>
                        <div class="flex justify-between items-center mt-1 text-xs text-gray-500 dark:text-gray-400">
                            <span>可用: ${free}</span>
                            <span>已用: ${used}</span>
                            <span>共计: ${total}</span>
                            ${error > 0 ? `<span class="text-red-600 dark:text-red-400">故障: ${error}</span>` : ''}
                        </div>
                    `}
                </div>
                
                <!-- 标签：校区和供应商 -->
                <div class="flex flex-wrap gap-2">
                    <span class="px-2 py-1 rounded-md text-xs font-medium bg-blue-50 dark:bg-blue-900/30 text-blue-700 dark:text-blue-300 border border-blue-200 dark:border-blue-800">${campusName}</span>
                    ${provider_name ? `<span class="px-2 py-1 rounded-md text-xs font-medium bg-slate-50 dark:bg-slate-800 text-slate-700 dark:text-slate-300 border border-slate-200 dark:border-slate-700 inline-flex items-center gap-1"><span class="text-[10px]">${shapeIcon}</span>${provider_name}</span>` : ''}
                </div>
            </div>
        `;
    }).join('');
    
    // 添加点击事件
    listEl.querySelectorAll('[data-name]').forEach(item => {
        const stationName = item.dataset.name;
        
        // 收藏图标点击事件（阻止冒泡，避免触发地图定位）
        const starIcon = item.querySelector('[data-devids]');
        if (starIcon) {
            starIcon.addEventListener('click', async (e) => {
                e.stopPropagation(); // 阻止事件冒泡
                e.preventDefault(); // 防止默认行为
                // 从 data 属性获取 devid 列表、devdescript 和 provider_id
                const devidsJson = starIcon.getAttribute('data-devids');
                const devdescript = starIcon.getAttribute('data-devdescript');
                
                // 优先从 data-provider-id 属性获取
                let providerId = item.getAttribute('data-provider-id');
                
                // 如果 data-provider-id 为空，尝试从当前站点数据中查找
                if (!providerId && window.currentStations) {
                    const station = window.currentStations.find(s => s.name === stationName);
                    if (station && station.provider_id) {
                        providerId = station.provider_id;
                    }
                }
                
                // 如果还是没有，尝试从 allStationsDef 中查找
                if (!providerId && window.allStationsDef) {
                    const stationDef = window.allStationsDef.find(def => {
                        const defName = def.devdescript || def.name;
                        return defName === stationName;
                    });
                    if (stationDef && stationDef.provider_id) {
                        providerId = stationDef.provider_id;
                    }
                }
                
                let devids = null;
                if (devidsJson && devidsJson !== 'null' && devidsJson !== '[]') {
                    try {
                        devids = JSON.parse(devidsJson);
                        // 确保 devids 是数组且不为空
                        if (!Array.isArray(devids) || devids.length === 0) {
                            devids = null;
                        }
                    } catch (error) {
                        console.error('解析 devids 失败:', error);
                        devids = null;
                    }
                }
                
                await toggleWatchlist(devids, devdescript, providerId);
            });
        }
        
        // 列表项点击事件，定位到地图（仅当已抓取到数据时）
        item.addEventListener('click', (e) => {
            // 如果点击的是关注图标或其子元素，不触发地图定位
            if (e.target.closest('[data-devids]')) {
                return;
            }
            
            // 如果未抓取到数据，不执行定位
            const isAvailable = item.getAttribute('data-available') === 'true';
            if (!isAvailable) {
                return;
            }
            
            const station = filteredStations.find(s => s.name === stationName);
            if (station) {
                // 坐标转换
                const [viewLat, viewLon] = convertCoord(station.lat, station.lon);
                map.setView([viewLat, viewLon], 17);
                // 打开对应的弹出窗口
                const marker = markers.find(m => {
                    const popup = m.getPopup();
                    return popup && popup.getContent().includes(stationName);
                });
                if (marker) {
                    marker.openPopup();
                }
            }
        });
    });
}

// 检查是否在夜间时段（0:10-5:50）
function isNightTime() {
    const now = new Date();
    const hours = now.getHours();
    const minutes = now.getMinutes();
    const currentTimeMinutes = hours * 60 + minutes;
    
    // 夜间时段：0:10 (10分钟) 到 5:50 (350分钟)
    const nightStartMinutes = 0 * 60 + 10; // 0:10
    const nightEndMinutes = 5 * 60 + 50;   // 5:50
    
    return currentTimeMinutes >= nightStartMinutes && currentTimeMinutes <= nightEndMinutes;
}

// 更新夜间消息显示状态
function updateNightMessage() {
    const nightMessageEl = document.getElementById('night-message');
    if (nightMessageEl) {
        if (isNightTime()) {
            nightMessageEl.classList.remove('hidden');
        } else {
            nightMessageEl.classList.add('hidden');
        }
    }
}

// 更新时间显示
function updateTime(timestamp) {
    const timeEl = document.getElementById('update-time');
    if (timestamp) {
        const date = new Date(timestamp);
        const timeStr = date.toLocaleString('zh-CN', {
            year: 'numeric',
            month: '2-digit',
            day: '2-digit',
            hour: '2-digit',
            minute: '2-digit',
            second: '2-digit'
        });
        timeEl.textContent = `更新时间: ${timeStr}`;
    } else {
        timeEl.textContent = '更新时间: 未知';
    }
    // 同时更新夜间消息显示状态
    updateNightMessage();
}

// 暗色模式相关函数
function getTheme() {
    return localStorage.getItem(THEME_STORAGE_KEY) || 'light';
}

function setTheme(theme) {
    localStorage.setItem(THEME_STORAGE_KEY, theme);
    if (theme === 'dark') {
        document.documentElement.classList.add('dark');
    } else {
        document.documentElement.classList.remove('dark');
    }
}

function toggleTheme() {
    const currentTheme = getTheme();
    const newTheme = currentTheme === 'dark' ? 'light' : 'dark';
    console.log(`切换主题: ${currentTheme} -> ${newTheme}`);
    setTheme(newTheme);
}

function initTheme() {
    const theme = getTheme();
    setTheme(theme);
}

// 校区切换事件
function setupCampusSelector() {
    const campusButtons = document.querySelectorAll('[data-campus]');
    campusButtons.forEach(btn => {
        btn.addEventListener('click', () => {
            // 更新所有按钮样式
            campusButtons.forEach(b => {
                if (b === btn) {
                    // 激活状态：蓝色背景
                    b.className = 'px-3 lg:px-4 py-2 rounded-md text-xs lg:text-sm font-medium transition-all duration-200 bg-blue-600 dark:bg-blue-500 text-white border border-blue-600 dark:border-blue-500 hover:bg-blue-700 dark:hover:bg-blue-600';
                } else {
                    // 非激活状态：灰色背景
                    b.className = 'px-3 lg:px-4 py-2 rounded-md text-xs lg:text-sm font-medium transition-all duration-200 bg-gray-100 dark:bg-gray-700 text-gray-700 dark:text-gray-200 border border-gray-300 dark:border-gray-600 hover:bg-blue-50 dark:hover:bg-blue-900/30 hover:border-blue-600 dark:hover:border-blue-500 hover:text-blue-600 dark:hover:text-blue-400';
                }
            });
            // 更新当前校区
            currentCampus = btn.dataset.campus || "";
            // 重新渲染（使用已加载的数据）
            // 校区切换时允许调整地图视野（传入 true）
            if (window.currentStations) {
                // 合并所有站点用于地图显示（包括未抓取的）
        const allStationsForMap = [...(window.currentStations || [])];
        if (window.allStationsDef && window.allStationsDef.length > 0) {
            const fetchedNames = new Set((window.currentStations || []).map(s => s.name));
            window.allStationsDef.forEach(def => {
                const devdescript = def.devdescript || def.name;
                if (!fetchedNames.has(devdescript)) {
                    const matchesProvider = !currentProvider || def.provider_id === currentProvider;
                    if (matchesProvider) {
                        allStationsForMap.push({
                            name: devdescript,
                            free: 0,
                            total: 0,
                            used: 0,
                            error: 0,
                            devids: def.devid ? [def.devid] : [],
                            provider_id: def.provider_id || 'unknown',
                            provider_name: def.provider_name || '未知',
                            campus: def.areaid,
                            lat: def.latitude,
                            lon: def.longitude,
                            isFetched: false
                        });
                    }
                }
            });
        }
        renderMap(allStationsForMap, true); // 校区切换时允许调整视野
                renderList(window.currentStations);
            }
        });
    });
}

// 服务商切换事件
function setupProviderSelector() {
    const providerSelector = document.getElementById('provider-selector');
    if (providerSelector) {
        providerSelector.addEventListener('change', (e) => {
            currentProvider = e.target.value || "";
            // 如果选择了服务商，需要重新获取数据
            if (currentProvider) {
                fetchStatus();
            } else {
                // 如果选择"全部"，使用已加载的数据重新渲染
                // 切换服务商时保持当前位置（false），因为用户可能已经定位到某个位置
                if (window.currentStations) {
                    // 合并所有站点用于地图显示（包括未抓取的）
        const allStationsForMap = [...(window.currentStations || [])];
        if (window.allStationsDef && window.allStationsDef.length > 0) {
            const fetchedNames = new Set((window.currentStations || []).map(s => s.name));
            window.allStationsDef.forEach(def => {
                const devdescript = def.devdescript || def.name;
                if (!fetchedNames.has(devdescript)) {
                    const matchesProvider = !currentProvider || def.provider_id === currentProvider;
                    if (matchesProvider) {
                        allStationsForMap.push({
                            name: devdescript,
                            free: 0,
                            total: 0,
                            used: 0,
                            error: 0,
                            devids: def.devid ? [def.devid] : [],
                            provider_id: def.provider_id || 'unknown',
                            provider_name: def.provider_name || '未知',
                            campus: def.areaid,
                            lat: def.latitude,
                            lon: def.longitude,
                            isFetched: false
                        });
                    }
                }
            });
        }
        renderMap(allStationsForMap, false); // 切换服务商时保持当前位置
                    renderList(window.currentStations, window.allStationsDef);
                }
            }
        });
    }
}

// 地图切换事件
const mapSelector = document.getElementById('map-selector');
if (mapSelector) {
    mapSelector.addEventListener('change', (e) => {
        const mapProvider = e.target.value;
        if (mapProvider && MAP_PROVIDERS[mapProvider]) {
            switchMap(mapProvider);
        }
    });
}

// 刷新按钮事件
document.getElementById('refresh-btn').addEventListener('click', () => {
    fetchStatus();
});

// 获取前端配置
let fetchInterval = 60; // 默认60秒

// 计算两点之间的距离（使用 Haversine 公式，单位：公里）
function calculateDistance(lat1, lon1, lat2, lon2) {
    const R = 6371; // 地球半径（公里）
    const dLat = (lat2 - lat1) * Math.PI / 180;
    const dLon = (lon2 - lon1) * Math.PI / 180;
    const a = 
        Math.sin(dLat / 2) * Math.sin(dLat / 2) +
        Math.cos(lat1 * Math.PI / 180) * Math.cos(lat2 * Math.PI / 180) *
        Math.sin(dLon / 2) * Math.sin(dLon / 2);
    const c = 2 * Math.atan2(Math.sqrt(a), Math.sqrt(1 - a));
    return R * c;
}

// 显示当前位置在地图上
function showCurrentLocation() {
    // 检查浏览器是否支持地理位置 API
    if (!navigator.geolocation) {
        alert('您的浏览器不支持地理位置服务');
        return;
    }

    // 检查是否在 HTTPS 环境下（localhost 除外）
    const isSecureContext = window.isSecureContext || location.protocol === 'https:' || location.hostname === 'localhost' || location.hostname === '127.0.0.1';
    if (!isSecureContext) {
        alert('地理位置功能需要 HTTPS 环境才能使用');
        return;
    }

    // 移除旧的当前位置标记
    if (currentLocationMarker) {
        map.removeLayer(currentLocationMarker);
        currentLocationMarker = null;
    }

    // 显示加载状态
    const locationBtn = document.getElementById('location-btn');
    if (locationBtn) {
        locationBtn.disabled = true;
        locationBtn.innerHTML = `
            <svg class="animate-spin" width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                <path d="M21 12a9 9 0 11-6.219-8.56"/>
            </svg>
            <span class="hidden sm:inline">定位中...</span>
        `;
    }

    navigator.geolocation.getCurrentPosition(
        (position) => {
            const userLat = position.coords.latitude;
            const userLon = position.coords.longitude;
            
            console.log(`当前位置: ${userLat}, ${userLon}`);
            
            // 坐标转换：用户位置通常是 WGS84，需要转换为地图使用的坐标系
            // convertCoord 函数期望输入是 [lng, lat] 格式，但数据源坐标系是 BD09
            // 我们需要创建一个从 WGS84 转换的函数
            let markerLat = userLat;
            let markerLon = userLon;
            
            // 如果地图使用的是 GCJ02 或 BD09，需要从 WGS84 转换
            const targetCoord = MAP_CONFIG.webCoordSystem;
            if (targetCoord === 'GCJ02') {
                // WGS84 -> GCJ02
                if (typeof wgs84ToGcj02 === 'function') {
                    const converted = wgs84ToGcj02(userLon, userLat);
                    markerLon = converted[0];
                    markerLat = converted[1];
                } else {
                    console.warn('wgs84ToGcj02 函数不可用，使用原始坐标');
                }
            } else if (targetCoord === 'BD09') {
                // WGS84 -> BD09
                if (typeof wgs84ToBd09 === 'function') {
                    const converted = wgs84ToBd09(userLon, userLat);
                    markerLon = converted[0];
                    markerLat = converted[1];
                } else {
                    console.warn('wgs84ToBd09 函数不可用，使用原始坐标');
                }
            }
            // 如果目标坐标系是 WGS84，不需要转换
            
            // 创建当前位置图标（蓝色圆点，带外圈）
            const locationIconHtml = `
                <div style="
                    width: 20px;
                    height: 20px;
                    background-color: #3b82f6;
                    border: 3px solid white;
                    border-radius: 50%;
                    box-shadow: 0 2px 8px rgba(0,0,0,0.3);
                    position: relative;
                ">
                    <div style="
                        position: absolute;
                        top: 50%;
                        left: 50%;
                        transform: translate(-50%, -50%);
                        width: 8px;
                        height: 8px;
                        background-color: white;
                        border-radius: 50%;
                    "></div>
                </div>
            `;
            
            const locationIcon = L.divIcon({
                html: locationIconHtml,
                className: '',
                iconSize: [20, 20],
                iconAnchor: [10, 10]
            });
            
            // 创建标记
            currentLocationMarker = L.marker([markerLat, markerLon], {
                icon: locationIcon,
                zIndexOffset: 1000 // 确保在充电桩标记之上
            }).addTo(map);
            
            // 添加弹出窗口
            currentLocationMarker.bindPopup(`
                <div style="text-align: center; width: fit-content;">
                    <strong style="font-size: 14px;">📍 当前位置</strong>
                </div>
            `).openPopup();
            
            // 定位到当前位置（带缩放）
            map.setView([markerLat, markerLon], 16);
            
            // 恢复按钮状态
            if (locationBtn) {
                locationBtn.disabled = false;
                locationBtn.innerHTML = `
                    <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
                        <path d="M21 10c0 7-9 13-9 13s-9-6-9-13a9 9 0 0 1 18 0z"></path>
                        <circle cx="12" cy="10" r="3"></circle>
                    </svg>
                    <span class="hidden sm:inline">定位</span>
                `;
            }
        },
        (error) => {
            let errorMessage = '获取位置失败';
            switch(error.code) {
                case error.PERMISSION_DENIED:
                    errorMessage = '您拒绝了位置权限请求，请在浏览器设置中允许位置访问';
                    break;
                case error.POSITION_UNAVAILABLE:
                    errorMessage = '位置信息不可用';
                    break;
                case error.TIMEOUT:
                    errorMessage = '获取位置超时，请重试';
                    break;
                default:
                    errorMessage = error.message || '未知错误';
                    break;
            }
            alert(errorMessage);
            console.error('获取位置失败:', errorMessage, error);
            
            // 恢复按钮状态
            if (locationBtn) {
                locationBtn.disabled = false;
                locationBtn.innerHTML = `
                    <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
                        <path d="M21 10c0 7-9 13-9 13s-9-6-9-13a9 9 0 0 1 18 0z"></path>
                        <circle cx="12" cy="10" r="3"></circle>
                    </svg>
                    <span class="hidden sm:inline">定位</span>
                `;
            }
        },
        {
            enableHighAccuracy: true,
            timeout: 10000,
            maximumAge: 0 // 不使用缓存，每次都获取最新位置
        }
    );
}

// 获取用户位置并找到最近的校区
function detectNearestCampus() {
    return new Promise((resolve, reject) => {
        // 检查浏览器是否支持地理位置 API
        if (!navigator.geolocation) {
            reject(new Error('浏览器不支持地理位置服务'));
            return;
        }

        // 检查是否在 HTTPS 环境下（localhost 除外）
        const isSecureContext = window.isSecureContext || location.protocol === 'https:' || location.hostname === 'localhost' || location.hostname === '127.0.0.1';
        if (!isSecureContext) {
            console.warn('地理位置 API 需要 HTTPS 环境才能使用');
            reject(new Error('地理位置功能需要 HTTPS 环境，当前为 HTTP'));
            return;
        }

        navigator.geolocation.getCurrentPosition(
            (position) => {
                const userLat = position.coords.latitude;
                const userLon = position.coords.longitude;
                
                console.log(`用户位置: ${userLat}, ${userLon}`);
                
                // 计算到各个校区的距离
                let nearestCampus = null;
                let minDistance = Infinity;
                
                for (const [campusId, campusInfo] of Object.entries(CAMPUS_CONFIG)) {
                    const [campusLon, campusLat] = campusInfo.center;
                    const distance = calculateDistance(userLat, userLon, campusLat, campusLon);
                    
                    console.log(`${campusInfo.name} 距离: ${distance.toFixed(2)} 公里`);
                    
                    if (distance < minDistance) {
                        minDistance = distance;
                        nearestCampus = {
                            id: campusId,
                            name: campusInfo.name,
                            distance: distance
                        };
                    }
                }
                
                if (nearestCampus) {
                    console.log(`最近的校区: ${nearestCampus.name} (${nearestCampus.distance.toFixed(2)} 公里)`);
                    resolve(nearestCampus);
                } else {
                    reject(new Error('无法找到最近的校区'));
                }
            },
            (error) => {
                let errorMessage = '获取位置失败';
                switch(error.code) {
                    case error.PERMISSION_DENIED:
                        errorMessage = '用户拒绝了位置权限请求';
                        break;
                    case error.POSITION_UNAVAILABLE:
                        errorMessage = '位置信息不可用';
                        break;
                    case error.TIMEOUT:
                        errorMessage = '获取位置超时';
                        break;
                    default:
                        errorMessage = error.message || '未知错误';
                        break;
                }
                console.warn('获取位置失败:', errorMessage, error);
                reject(new Error(errorMessage));
            },
            {
                enableHighAccuracy: false,
                timeout: 10000, // 增加到10秒
                maximumAge: 60000 // 缓存1分钟
            }
        );
    });
}

// 显示位置提醒通知
function showLocationNotification(campusName, distance, isSwitched = false) {
    // 移除已存在的通知
    const existingNotification = document.getElementById('location-notification');
    if (existingNotification) {
        existingNotification.remove();
    }
    
    // 创建通知元素
    const notification = document.createElement('div');
    notification.id = 'location-notification';
    notification.className = 'fixed top-4 right-4 bg-blue-50 dark:bg-blue-900/30 border border-blue-200 dark:border-blue-800 rounded-lg shadow-lg p-4 max-w-sm z-[9999] animate-slide-in';
    notification.style.zIndex = '9999'; // 确保在最上层
    const distanceText = distance !== undefined ? ` (距离您约 ${distance.toFixed(1)} 公里)` : '';
    const titleText = isSwitched ? '已自动切换到最近校区' : '检测到您的位置';
    notification.innerHTML = `
        <div class="flex items-start gap-3">
            <div class="flex-shrink-0">
                <svg class="w-6 h-6 text-blue-600 dark:text-blue-400" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                    <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M17.657 16.657L13.414 20.9a1.998 1.998 0 01-2.827 0l-4.244-4.243a8 8 0 1111.314 0z"></path>
                    <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M15 11a3 3 0 11-6 0 3 3 0 016 0z"></path>
                </svg>
            </div>
            <div class="flex-1">
                <p class="text-sm font-medium text-blue-900 dark:text-blue-200">${titleText}</p>
                <p class="text-xs text-blue-700 dark:text-blue-300 mt-1">${campusName}${distanceText}</p>
            </div>
            <button onclick="this.parentElement.parentElement.remove()" class="flex-shrink-0 text-blue-400 dark:text-blue-500 hover:text-blue-600 dark:hover:text-blue-400">
                <svg class="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                    <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M6 18L18 6M6 6l12 12"></path>
                </svg>
            </button>
        </div>
    `;
    
    // 添加样式（如果还没有）
    if (!document.getElementById('location-notification-style')) {
        const style = document.createElement('style');
        style.id = 'location-notification-style';
        style.textContent = `
            @keyframes slide-in {
                from {
                    transform: translateX(100%);
                    opacity: 0;
                }
                to {
                    transform: translateX(0);
                    opacity: 1;
                }
            }
            .animate-slide-in {
                animation: slide-in 0.3s ease-out;
            }
        `;
        document.head.appendChild(style);
    }
    
    document.body.appendChild(notification);
    
    // 5秒后自动消失
    setTimeout(() => {
        if (notification.parentElement) {
            notification.style.transition = 'opacity 0.3s ease-out';
            notification.style.opacity = '0';
            setTimeout(() => {
                if (notification.parentElement) {
                    notification.remove();
                }
            }, 300);
        }
    }, 5000);
}

// 切换到指定校区
function switchToCampus(campusId) {
    const campusInfo = CAMPUS_CONFIG[campusId];
    if (!campusInfo) {
        console.error(`未知的校区 ID: ${campusId}`);
        return;
    }
    
    // 更新当前校区
    currentCampus = campusId;
    
            // 更新按钮样式
    const campusButtons = document.querySelectorAll('[data-campus]');
    campusButtons.forEach(btn => {
        if (btn.dataset.campus === campusId) {
            btn.className = 'px-3 lg:px-4 py-2 rounded-md text-xs lg:text-sm font-medium transition-all duration-200 bg-blue-600 dark:bg-blue-500 text-white border border-blue-600 dark:border-blue-500 hover:bg-blue-700 dark:hover:bg-blue-600';
        } else {
            btn.className = 'px-3 lg:px-4 py-2 rounded-md text-xs lg:text-sm font-medium transition-all duration-200 bg-gray-100 dark:bg-gray-700 text-gray-700 dark:text-gray-200 border border-gray-300 dark:border-gray-600 hover:bg-blue-50 dark:hover:bg-blue-900/30 hover:border-blue-600 dark:hover:border-blue-500 hover:text-blue-600 dark:hover:text-blue-400';
        }
    });
    
    // 重新渲染地图和列表
    // 切换校区时允许调整视野（true），因为用户主动切换了校区
    if (window.currentStations) {
        const allStationsForMap = [...(window.currentStations || [])];
        if (window.allStationsDef && window.allStationsDef.length > 0) {
            const fetchedNames = new Set((window.currentStations || []).map(s => s.name));
            window.allStationsDef.forEach(def => {
                const devdescript = def.devdescript || def.name;
                if (!fetchedNames.has(devdescript)) {
                    const matchesProvider = !currentProvider || def.provider_id === currentProvider;
                    if (matchesProvider) {
                        allStationsForMap.push({
                            name: devdescript,
                            free: 0,
                            total: 0,
                            used: 0,
                            error: 0,
                            devids: def.devid ? [def.devid] : [],
                            provider_id: def.provider_id || 'unknown',
                            provider_name: def.provider_name || '未知',
                            campus: def.areaid,
                            lat: def.latitude,
                            lon: def.longitude,
                            isFetched: false
                        });
                    }
                }
            });
        }
        renderMap(allStationsForMap, true); // 切换校区时允许调整视野
        renderList(window.currentStations, window.allStationsDef);
    }
}

async function loadConfig() {
    try {
        const response = await fetch('/api/config');
        if (response.status === 429) {
            // 限流错误
            showRateLimitAlert();
            return false;
        }
        if (response.ok) {
            const config = await response.json();
            fetchInterval = config.fetch_interval || 60;
            console.log(`已加载配置：自动刷新间隔 = ${fetchInterval}秒`);
            return true;
        }
    } catch (error) {
        console.warn('获取配置失败，使用默认值:', error);
    }
    return false;
}

// 页面加载时初始化
document.addEventListener('DOMContentLoaded', async () => {
    // 初始化暗色模式
    initTheme();
    
    // 设置暗色模式切换按钮事件
    const themeToggle = document.getElementById('theme-toggle');
    if (themeToggle) {
        themeToggle.addEventListener('click', (e) => {
            e.preventDefault();
            e.stopPropagation();
            console.log('主题切换按钮被点击');
            toggleTheme();
        });
        console.log('暗色模式切换按钮已绑定事件');
    } else {
        console.error('未找到主题切换按钮');
    }
    
    // 默认校区为玉泉校区
    currentCampus = "2143";
    
    initMap();
    setupCampusSelector();
    setupProviderSelector();
    // 初始化地图选择器状态
    updateMapSelector();
    // 设置默认校区为玉泉校区按钮样式
    const yuquanButton = document.getElementById('campus-yuquan');
    const allButton = document.getElementById('campus-all');
    const zjgButton = document.getElementById('campus-zjg');
    if (yuquanButton) {
        // 更新按钮样式为激活状态
        yuquanButton.className = 'px-3 lg:px-4 py-2 rounded-md text-xs lg:text-sm font-medium transition-all duration-200 bg-blue-600 dark:bg-blue-500 text-white border border-blue-600 dark:border-blue-500 hover:bg-blue-700 dark:hover:bg-blue-600';
    }
    if (allButton) {
        allButton.className = 'px-3 lg:px-4 py-2 rounded-md text-xs lg:text-sm font-medium transition-all duration-200 bg-gray-100 dark:bg-gray-700 text-gray-700 dark:text-gray-200 border border-gray-300 dark:border-gray-600 hover:bg-blue-50 dark:hover:bg-blue-900/30 hover:border-blue-600 dark:hover:border-blue-500 hover:text-blue-600 dark:hover:text-blue-400';
    }
    if (zjgButton) {
        zjgButton.className = 'px-3 lg:px-4 py-2 rounded-md text-xs lg:text-sm font-medium transition-all duration-200 bg-gray-100 dark:bg-gray-700 text-gray-700 dark:text-gray-200 border border-gray-300 dark:border-gray-600 hover:bg-blue-50 dark:hover:bg-blue-900/30 hover:border-blue-600 dark:hover:border-blue-500 hover:text-blue-600 dark:hover:text-blue-400';
    }
    
    // 尝试自动检测最近的校区
    try {
        const nearestCampus = await detectNearestCampus();
        if (nearestCampus) {
            console.log(`检测到最近校区: ${nearestCampus.name}, 当前校区: ${currentCampus}`);
            const isSwitched = nearestCampus.id !== currentCampus;
            if (isSwitched) {
                // 切换到最近的校区
                console.log(`切换到最近校区: ${nearestCampus.name}`);
                switchToCampus(nearestCampus.id);
            }
            // 无论是否切换，都显示通知（让用户知道检测到了位置）
            console.log(`显示通知: ${nearestCampus.name}, 距离: ${nearestCampus.distance.toFixed(2)} 公里, 已切换: ${isSwitched}`);
            showLocationNotification(nearestCampus.name, nearestCampus.distance, isSwitched);
        } else {
            console.warn('未找到最近校区');
        }
    } catch (error) {
        console.log('自动检测校区失败，使用默认校区:', error.message);
        console.log('错误详情:', error);
        
        // 如果是 HTTPS 相关错误，显示友好提示
        if (error.message && error.message.includes('HTTPS')) {
            console.warn('提示: 地理位置功能需要 HTTPS 环境。当前网站使用 HTTP，无法获取位置信息。');
        } else if (error.message && error.message.includes('权限')) {
            console.warn('提示: 用户拒绝了位置权限，无法自动检测最近校区。');
        }
        // 为了不打扰用户，这里不显示错误通知，静默使用默认校区
    }
    
    // 加载配置
    await loadConfig();
    // 先加载服务商列表
    await loadProviders();
    // 先加载关注列表（从 localStorage），再获取站点状态
    fetchWatchlist();
    // 确保在 fetchStatus 执行时 currentCampus 仍然是正确的值
    await fetchStatus();
    
    // 初始化夜间消息显示状态
    updateNightMessage();
    
    // 设置定时检查夜间消息（每分钟检查一次）
    setInterval(() => {
        updateNightMessage();
    }, 60 * 1000); // 60秒 = 1分钟
    
    // 设置定位按钮事件
    const locationBtn = document.getElementById('location-btn');
    if (locationBtn) {
        locationBtn.addEventListener('click', function() {
            showCurrentLocation();
        });
    }
    
    // 设置下载按钮事件
    const downloadBtn = document.getElementById('download-map-btn');
    if (downloadBtn) {
        downloadBtn.addEventListener('click', function() {
            manualPrint();
        });
    }
    
    // 使用配置的间隔自动刷新
    setInterval(() => {
        fetchWatchlist(); // 从 localStorage 读取，不需要 await
        fetchStatus();
    }, fetchInterval * 1000); // 转换为毫秒
});
