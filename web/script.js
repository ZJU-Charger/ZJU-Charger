// 地图和标记
let map = null;
let markers = [];

// 当前选中的校区 areaid（空字符串表示全部）
let currentAreaId = "";

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
    
    // 更新按钮状态
    updateMapSwitchButtons();
    
    // 重新转换并设置中心点
    const center = convertCoord(DEFAULT_CENTER[0], DEFAULT_CENTER[1]);
    map.setView(center, map.getZoom());
    
    // 重新渲染所有标记（因为坐标系改变了）
    if (window.currentStations && window.currentStations.length > 0) {
        renderMap(window.currentStations);
    }
    
    console.log(`已切换到: ${provider.name} (${provider.coordSystem})`);
}

// 更新地图切换按钮状态
function updateMapSwitchButtons() {
    const buttons = document.querySelectorAll('.map-switch-btn');
    buttons.forEach(btn => {
        if (btn.dataset.map === MAP_CONFIG.useMap) {
            btn.classList.add('active');
        } else {
            btn.classList.remove('active');
        }
    });
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

// 获取站点状态
async function fetchStatus() {
    const loadingEl = document.getElementById('loading');
    const listEl = document.getElementById('station-list');
    
    loadingEl.style.display = 'block';
    listEl.innerHTML = '';
    
    try {
        // 先尝试调用 API
        let data;
        try {
            const response = await fetch('/api/status');
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
            } else {
                throw new Error('无法加载数据');
            }
        }
        
        if (data && data.stations) {
            if (data.stations.length === 0) {
                // 数据为空，显示提示
                const listEl = document.getElementById('station-list');
                listEl.innerHTML = `
                    <div class="error-message">
                        <p>暂无站点数据</p>
                        <p style="font-size: 12px; margin-top: 8px;">请确保已配置 OPENID 并成功抓取数据</p>
                        <p style="font-size: 12px; margin-top: 4px;">如果服务器正在运行，请检查控制台错误信息</p>
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
            <div class="error-message">
                <p>加载数据失败</p>
                <p style="font-size: 12px; margin-top: 8px;">${error.message}</p>
                <p style="font-size: 12px; margin-top: 8px; color: #666;">
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
    if (!currentAreaId) {
        return stations;  // 显示全部
    }
    return stations.filter(s => s.areaid && s.areaid.toString() === currentAreaId);
}

// 渲染地图
function renderMap(stations) {
    // 清除现有标记
    markers.forEach(marker => map.removeLayer(marker));
    markers = [];
    
    // 按校区过滤
    const filteredStations = filterStationsByCampus(stations);
    
    // 只显示有空闲的站点
    const availableStations = filteredStations.filter(s => s.free > 0);
    
    availableStations.forEach(station => {
        const { name, lat, lon, free, total } = station;
        
        // 坐标转换
        const [markerLat, markerLon] = convertCoord(lat, lon);
        
        // 根据空闲数量选择颜色
        let color = '#52c41a'; // 绿色：有空闲
        if (free <= 2) {
            color = '#faad14'; // 橙色：少量空闲
        }
        
        // 创建标记
        const marker = L.circleMarker([markerLat, markerLon], {
            radius: 8,
            fillColor: color,
            color: '#fff',
            weight: 2,
            opacity: 1,
            fillOpacity: 0.8
        }).addTo(map);
        
        // 添加弹出窗口
        marker.bindPopup(`
            <div style="text-align: center;">
                <strong>${name}</strong><br>
                可用: <span style="color: #52c41a; font-weight: bold;">${free}</span> / ${total}
            </div>
        `);
        
        markers.push(marker);
    });
    
    // 如果有标记，调整地图视野
    if (markers.length > 0) {
        const group = new L.featureGroup(markers);
        map.fitBounds(group.getBounds().pad(0.1));
    } else if (currentAreaId && CAMPUS_CONFIG[currentAreaId]) {
        // 如果没有标记但选择了校区，定位到校区中心
        const campus = CAMPUS_CONFIG[currentAreaId];
        const center = convertCoord(campus.center[0], campus.center[1]);
        map.setView(center, DEFAULT_ZOOM);
    }
}

// 渲染列表
function renderList(stations) {
    const listEl = document.getElementById('station-list');
    
    // 按校区过滤
    const filteredStations = filterStationsByCampus(stations);
    
    // 按空闲数量排序
    const sortedStations = [...filteredStations].sort((a, b) => b.free - a.free);
    
    if (sortedStations.length === 0) {
        listEl.innerHTML = '<div class="error-message">暂无站点数据</div>';
        return;
    }
    
    listEl.innerHTML = sortedStations.map(station => {
        const { name, free, total, used, error, devids } = station;
        
        // 确定状态样式
        let statusClass = 'none';
        let statusText = '无空闲';
        if (free > 0) {
            if (free <= 2) {
                statusClass = 'low';
                statusText = `仅${free}个`;
            } else {
                statusClass = 'free';
                statusText = `${free}个可用`;
            }
        }
        
        const itemClass = free === 0 ? 'station-item no-free' : 'station-item';
        
        // 检查是否已关注（检查 devid 或 devdescript）
        const stationDevids = devids || [];
        const watched = isWatched(stationDevids, name);
        const heartClass = watched ? 'heart-icon watched' : 'heart-icon';
        const heartSymbol = watched ? '❤️' : '🤍';
        
        // 将 devids 转换为 JSON 字符串以便在 data 属性中使用
        const devidsJson = JSON.stringify(stationDevids);
        
        return `
            <div class="${itemClass}" data-name="${name}">
                <div class="station-header">
                    <span class="station-name">${name}</span>
                    <span class="station-status ${statusClass}">${statusText}</span>
                    <span class="${heartClass}" data-devids='${devidsJson}' data-devdescript="${name}" title="${watched ? '取消关注' : '添加关注'}">${heartSymbol}</span>
                </div>
                <div class="station-info">
                    <span>可用: <strong>${free}</strong></span>
                    <span>已用: <strong>${used}</strong></span>
                    <span>总数: <strong>${total}</strong></span>
                    ${error > 0 ? `<span style="color: #ff4d4f;">故障: <strong>${error}</strong></span>` : ''}
                </div>
            </div>
        `;
    }).join('');
    
    // 添加点击事件
    listEl.querySelectorAll('.station-item').forEach(item => {
        const stationName = item.dataset.name;
        
        // 小红心点击事件（阻止冒泡，避免触发地图定位）
        const heartIcon = item.querySelector('.heart-icon');
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
        
        // 列表项点击事件，定位到地图
        item.addEventListener('click', (e) => {
            // 如果点击的是小红心，不触发地图定位
            if (e.target.classList.contains('heart-icon')) {
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
    const campusButtons = document.querySelectorAll('.campus-btn');
    campusButtons.forEach(btn => {
        btn.addEventListener('click', () => {
            // 移除所有 active 类
            campusButtons.forEach(b => b.classList.remove('active'));
            // 添加 active 类到当前按钮
            btn.classList.add('active');
            // 更新当前校区
            currentAreaId = btn.dataset.areaid || "";
            // 重新渲染（使用已加载的数据）
            if (window.currentStations) {
                renderMap(window.currentStations);
                renderList(window.currentStations);
            }
        });
    });
}

// 地图切换事件
document.querySelectorAll('.map-switch-btn').forEach(btn => {
    btn.addEventListener('click', () => {
        const mapProvider = btn.dataset.map;
        if (mapProvider && MAP_PROVIDERS[mapProvider]) {
            switchMap(mapProvider);
        }
    });
});

// 刷新按钮事件
document.getElementById('refresh-btn').addEventListener('click', () => {
    fetchStatus();
});

// 页面加载时初始化
document.addEventListener('DOMContentLoaded', async () => {
    initMap();
    setupCampusSelector();
    // 初始化地图切换按钮状态
    updateMapSwitchButtons();
    // 先加载关注列表，再获取站点状态
    await fetchWatchlist();
    fetchStatus();
    
    // 每60秒自动刷新
    setInterval(async () => {
        await fetchWatchlist();
        fetchStatus();
    }, 60000);
});
