// 地图和标记
let map = null;
let markers = [];

// 当前选中的校区 campus（空字符串表示全部）
let currentCampus = "";

// 当前选中的服务商（空字符串表示全部）
let currentProvider = "";

// 可用服务商列表
let availableProviders = [];

// 关注列表（devid 和 devdescript 集合）
let watchlistDevids = new Set();
let watchlistDevdescripts = new Set();

// 校区配置
const CAMPUS_CONFIG = {
    2143: { name: "玉泉校区", center: [30.27, 120.12] },
    1774: { name: "紫金港校区", center: [30.299196, 120.089946] }
};

// 默认中心点：玉泉校区（BD-09 坐标，会自动转换为 GCJ-02）
const DEFAULT_CENTER = [30.27, 120.12];
const DEFAULT_ZOOM = 15;

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
            minZoom: 1,
            maxZoom: 19,
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

// 初始化地图
function initMap() {
    // 如果地图已存在，先移除
    if (map) {
        map.remove();
    }
    
    // 转换中心点坐标
    const center = convertCoord(DEFAULT_CENTER[0], DEFAULT_CENTER[1]);
    
    // 创建地图实例
    map = L.map('map').setView(center, DEFAULT_ZOOM);
    
    // 添加当前配置的地图图层
    switchMap(MAP_CONFIG.useMap);
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
    
    // 更新配置
    MAP_CONFIG.useMap = mapProvider;
    const provider = MAP_PROVIDERS[mapProvider];
    MAP_CONFIG.webCoordSystem = provider.coordSystem;
    
    // 创建新图层
    currentTileLayer = L.tileLayer(provider.tileLayer, provider.options);
    currentTileLayer.addTo(map);
    
    // 更新选择器状态
    updateMapSelector();
    
    // 重新转换并设置中心点
    const center = convertCoord(DEFAULT_CENTER[0], DEFAULT_CENTER[1]);
    map.setView(center, map.getZoom());
    
    // 重新渲染所有标记（因为坐标系改变了）
    if (window.currentStations && window.currentStations.length > 0) {
        renderMap(window.currentStations);
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

// 获取关注列表
async function fetchWatchlist() {
    try {
        const response = await fetch('/api/watchlist/list');
        if (response.ok) {
            const data = await response.json();
            // 将 devid 列表转换为 Set（确保类型一致，使用数字）
            watchlistDevids = new Set((data.devids || []).map(d => parseInt(d)));
            // 将 devdescript 列表转换为 Set
            watchlistDevdescripts = new Set(data.devdescripts || []);
            return true;
        }
    } catch (error) {
        console.error('获取关注列表失败:', error);
    }
    return false;
}

// 检查是否已关注
function isWatched(devids, devdescript) {
    // 检查 devid
    if (devids && devids.length > 0) {
        const hasDevid = devids.some(devid => watchlistDevids.has(parseInt(devid)));
        if (hasDevid) return true;
    }
    // 检查 devdescript
    if (devdescript && watchlistDevdescripts.has(devdescript)) {
        return true;
    }
    return false;
}

// 切换关注状态
async function toggleWatchlist(devids, devdescript) {
    const currentlyWatched = isWatched(devids, devdescript);
    
    try {
        let response;
        const requestBody = {};
        if (devids && devids.length > 0) {
            requestBody.devids = Array.isArray(devids) ? devids : [devids];
        }
        if (devdescript) {
            requestBody.devdescripts = [devdescript];
        }
        
        if (currentlyWatched) {
            // 移除关注
            response = await fetch('/api/watchlist', {
                method: 'DELETE',
                headers: {
                    'Content-Type': 'application/json'
                },
                body: JSON.stringify(requestBody)
            });
        } else {
            // 添加关注
            response = await fetch('/api/watchlist', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json'
                },
                body: JSON.stringify(requestBody)
            });
        }
        
        if (response.ok) {
            const result = await response.json();
            if (result.success !== false) {
                // 更新本地关注列表
                if (currentlyWatched) {
                    // 移除
                    if (devids && devids.length > 0) {
                        devids.forEach(devid => watchlistDevids.delete(parseInt(devid)));
                    }
                    if (devdescript) {
                        watchlistDevdescripts.delete(devdescript);
                    }
                } else {
                    // 添加
                    if (devids && devids.length > 0) {
                        devids.forEach(devid => watchlistDevids.add(parseInt(devid)));
                    }
                    if (devdescript) {
                        watchlistDevdescripts.add(devdescript);
                    }
                }
                // 重新渲染列表以更新小红心状态
                if (window.currentStations) {
                    renderList(window.currentStations);
                }
                return true;
            } else {
                console.warn('操作失败:', result.message);
                return false;
            }
        } else {
            const error = await response.json();
            console.error('操作失败:', error.detail || '未知错误');
            alert(`操作失败: ${error.detail || '未知错误'}`);
            return false;
        }
    } catch (error) {
        console.error('切换关注状态失败:', error);
        alert(`操作失败: ${error.message}`);
        return false;
    }
}

// 加载可用服务商列表
async function loadProviders() {
    try {
        const response = await fetch('/api/providers');
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
        
        if (data && data.stations) {
            if (data.stations.length === 0) {
                // 数据为空，显示提示
                const listEl = document.getElementById('station-list');
                listEl.innerHTML = `
                    <div class="bg-red-50 border border-red-200 text-red-800 p-4 rounded-lg text-center">
                        <p class="font-medium">暂无站点数据</p>
                        <p class="text-sm mt-2">请确保已配置 OPENID 并成功抓取数据</p>
                        <p class="text-sm mt-1 text-red-600">如果服务器正在运行，请检查控制台错误信息</p>
                    </div>
                `;
                updateTime(data.updated_at || '未知');
            } else {
                // 保存当前数据供校区切换使用
                window.currentStations = data.stations;
                renderMap(data.stations);
                renderList(data.stations);
                updateTime(data.updated_at);
            }
        } else {
            throw new Error('数据格式错误：缺少 stations 字段');
        }
    } catch (error) {
        console.error('获取数据失败:', error);
        listEl.innerHTML = `
            <div class="bg-red-50 border border-red-200 text-red-800 p-4 rounded-lg text-center">
                <p class="font-medium">加载数据失败</p>
                <p class="text-sm mt-2">${error.message}</p>
                <p class="text-sm mt-2 text-red-600">
                    请检查：<br>
                    1. 服务器是否正在运行<br>
                    2. OPENID 环境变量是否已配置<br>
                    3. 网络连接是否正常<br>
                    4. 查看浏览器控制台获取详细错误信息
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
    return stations.filter(s => s.campus && s.campus.toString() === currentCampus);
}

// 过滤站点（按服务商）
function filterStationsByProvider(stations) {
    if (!currentProvider) {
        return stations;  // 显示全部
    }
    return stations.filter(s => s.provider_id === currentProvider);
}

// 渲染地图
function renderMap(stations) {
    // 清除现有标记
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
    
    // 显示所有站点（包括非空闲的）
    filteredStations.forEach(station => {
        const { name, lat, lon, free, total, provider_id, provider_name } = station;
        
        // 坐标转换
        const [markerLat, markerLon] = convertCoord(lat, lon);
        
        // 根据空闲数量选择颜色（统一的颜色方案）
        let color = '#10b981'; // 绿色：有空闲（更柔和的绿色）
        if (free === 0) {
            color = '#ef4444'; // 红色：无空闲
        } else if (free <= 2) {
            color = '#f59e0b'; // 橙色：少量空闲
        }
        
        // 获取服务商对应的形状
        const shape = providerShapes[provider_id] || 'circle';
        
        // 创建带数字的自定义图标（使用不同形状）
        const iconHtml = createMarkerIcon(color, shape, free);
        
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
        
        markers.push(marker);
    });
    
    // 如果有标记，调整地图视野
    if (markers.length > 0) {
        const group = new L.featureGroup(markers);
        map.fitBounds(group.getBounds().pad(0.1));
    } else if (currentCampus && CAMPUS_CONFIG[currentCampus]) {
        // 如果没有标记但选择了校区，定位到校区中心
        const campus = CAMPUS_CONFIG[currentCampus];
        const center = convertCoord(campus.center[0], campus.center[1]);
        map.setView(center, DEFAULT_ZOOM);
    }
}

// 渲染列表
function renderList(stations) {
    const listEl = document.getElementById('station-list');
    
    // 按校区和服务商过滤
    let filteredStations = filterStationsByCampus(stations);
    filteredStations = filterStationsByProvider(filteredStations);
    
    // 按空闲数量排序
    const sortedStations = [...filteredStations].sort((a, b) => b.free - a.free);
    
    if (sortedStations.length === 0) {
        listEl.innerHTML = '<div class="bg-red-50 border border-red-200 text-red-800 p-4 rounded-lg text-center">暂无站点数据</div>';
        return;
    }
    
    listEl.innerHTML = sortedStations.map(station => {
        const { name, free, total, used, error, devids, provider_id, provider_name, campus } = station;
        
        // 计算使用率
        const usagePercent = total > 0 ? (used / total) * 100 : 0;
        const freePercent = total > 0 ? (free / total) * 100 : 0;
        const errorPercent = total > 0 ? (error / total) * 100 : 0;
        
        // 可用部分统一使用绿色
        const barColor = '#10b981'; // 绿色：可用部分统一颜色
        
        // 检查是否没有可用充电桩
        const isUnavailable = free === 0;
        
        // 优化背景和边框配色
        const itemBgClass = 'bg-white';
        const itemBorderClass = 'border-gray-200';
        const itemHoverBorderClass = isUnavailable ? '' : 'hover:border-blue-400';
        const itemHoverBgClass = isUnavailable ? '' : 'hover:bg-blue-50';
        const cursorClass = isUnavailable ? 'cursor-not-allowed' : 'cursor-pointer';
        const grayscaleClass = isUnavailable ? 'grayscale opacity-60' : '';
        const hoverEffect = isUnavailable ? '' : 'hover:translate-x-1 hover:shadow-md';
        
        // 检查是否已关注
        const stationDevids = devids || [];
        const watched = isWatched(stationDevids, name);
        const heartAnimationClass = watched ? 'animate-pulse' : '';
        const heartSymbol = watched ? '❤️' : '🤍';
        
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
        
        return `
            <div class="p-4 border ${itemBorderClass} rounded-lg ${itemBgClass} transition-all duration-200 ${cursorClass} ${itemHoverBorderClass} ${itemHoverBgClass} ${hoverEffect} ${grayscaleClass}" data-name="${name}" data-available="${!isUnavailable}" title="${isUnavailable ? '暂无可用充电桩' : name}">
                <!-- 站点名称和关注按钮 -->
                <div class="flex justify-between items-start mb-3 gap-2">
                    <span class="font-semibold text-base text-gray-900 truncate flex-1" title="${name}">${displayName}</span>
                    <span class="text-lg cursor-pointer select-none transition-transform duration-200 hover:scale-125 flex-shrink-0 p-0.5 leading-none ${heartAnimationClass}" data-devids='${devidsJson}' data-devdescript="${name}" title="${watched ? '取消关注' : '添加关注'}">${heartSymbol}</span>
                </div>
                
                <!-- 颜色条：显示使用情况（可用部分在最左侧） -->
                <div class="mb-3">
                    <div class="h-3 bg-gray-200 rounded-full overflow-hidden flex">
                        ${free > 0 ? `<div style="background-color: ${barColor}; width: ${freePercent}%"></div>` : ''}
                        ${used > 0 ? `<div class="bg-gray-400" style="width: ${usagePercent}%"></div>` : ''}
                        ${error > 0 ? `<div class="bg-red-500" style="width: ${errorPercent}%"></div>` : ''}
                    </div>
                    <div class="flex justify-between items-center mt-1 text-xs text-gray-500">
                        <span>可用: ${free}</span>
                        <span>已用: ${used}</span>
                        <span>共计: ${total}</span>
                        ${error > 0 ? `<span class="text-red-600">故障: ${error}</span>` : ''}
                    </div>
                </div>
                
                <!-- 标签：校区和供应商 -->
                <div class="flex flex-wrap gap-2">
                    <span class="px-2 py-1 rounded-md text-xs font-medium bg-blue-50 text-blue-700 border border-blue-200">${campusName}</span>
                    ${provider_name ? `<span class="px-2 py-1 rounded-md text-xs font-medium bg-slate-50 text-slate-700 border border-slate-200 inline-flex items-center gap-1"><span class="text-[10px]">${shapeIcon}</span>${provider_name}</span>` : ''}
                </div>
            </div>
        `;
    }).join('');
    
    // 添加点击事件
    listEl.querySelectorAll('[data-name]').forEach(item => {
        const stationName = item.dataset.name;
        
        // 小红心点击事件（阻止冒泡，避免触发地图定位）
        const heartIcon = item.querySelector('[data-devids]');
        if (heartIcon) {
            heartIcon.addEventListener('click', async (e) => {
                e.stopPropagation(); // 阻止事件冒泡
                // 从 data 属性获取 devid 列表和 devdescript
                const devidsJson = heartIcon.getAttribute('data-devids');
                const devdescript = heartIcon.getAttribute('data-devdescript');
                
                let devids = null;
                if (devidsJson) {
                    try {
                        devids = JSON.parse(devidsJson);
                    } catch (error) {
                        console.error('解析 devids 失败:', error);
                    }
                }
                
                await toggleWatchlist(devids, devdescript);
            });
        }
        
        // 列表项点击事件，定位到地图（仅当有可用充电桩时）
        item.addEventListener('click', (e) => {
            // 如果点击的是小红心，不触发地图定位
            if (e.target.hasAttribute('data-devids')) {
                return;
            }
            
            // 如果没有可用充电桩，不执行定位
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
                    b.className = 'px-3 lg:px-4 py-2 rounded-md text-xs lg:text-sm font-medium transition-all duration-200 bg-blue-600 text-white border border-blue-600 hover:bg-blue-700';
                } else {
                    // 非激活状态：灰色背景
                    b.className = 'px-3 lg:px-4 py-2 rounded-md text-xs lg:text-sm font-medium transition-all duration-200 bg-gray-100 text-gray-700 border border-gray-300 hover:bg-blue-50 hover:border-blue-600 hover:text-blue-600';
                }
            });
            // 更新当前校区
            currentCampus = btn.dataset.campus || "";
            // 重新渲染（使用已加载的数据）
            if (window.currentStations) {
                renderMap(window.currentStations);
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
                if (window.currentStations) {
                    renderMap(window.currentStations);
                    renderList(window.currentStations);
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

async function loadConfig() {
    try {
        const response = await fetch('/api/config');
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
    initMap();
    setupCampusSelector();
    setupProviderSelector();
    // 初始化地图选择器状态
    updateMapSelector();
    // 加载配置
    await loadConfig();
    // 先加载服务商列表
    await loadProviders();
    // 先加载关注列表，再获取站点状态
    await fetchWatchlist();
    fetchStatus();
    
    // 使用配置的间隔自动刷新
    setInterval(async () => {
        await fetchWatchlist();
        fetchStatus();
    }, fetchInterval * 1000); // 转换为毫秒
});
