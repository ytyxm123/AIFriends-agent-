"""Weather MCP server using Open-Meteo's non-commercial public APIs.

Run with the project Python interpreter over stdio. Never print to stdout:
it carries MCP protocol messages. No Django configuration or API key required.
"""
import asyncio
from typing import Annotated

import httpx
from mcp.server.fastmcp import FastMCP
from mcp.server.fastmcp.exceptions import ToolError
from pydantic import Field

mcp = FastMCP('AIFriends Weather')

WEATHER_CODES = {
    0: '晴', 1: '大部晴朗', 2: '局部多云', 3: '阴',
    45: '雾', 48: '雾凇', 51: '小毛毛雨', 53: '毛毛雨', 55: '强毛毛雨',
    56: '轻度冻毛毛雨', 57: '强冻毛毛雨', 61: '小雨', 63: '中雨', 65: '大雨',
    66: '轻度冻雨', 67: '强冻雨', 71: '小雪', 73: '中雪', 75: '大雪',
    77: '雪粒', 80: '小阵雨', 81: '中阵雨', 82: '强阵雨',
    85: '小阵雪', 86: '强阵雪', 95: '雷暴', 96: '雷暴伴小冰雹', 99: '雷暴伴强冰雹',
}


async def fetch_weather(city: str, days: int = 3, country_code: str = 'CN') -> dict:
    """Resolve a city and retrieve a bounded forecast in under 18 seconds."""
    city = city.strip()
    country_code = country_code.strip().upper()
    if not city or len(city) > 100:
        raise ToolError('请输入具体城市名称，长度不能超过100字。')
    if not 1 <= days <= 7:
        raise ToolError('预报天数必须为1到7天。')
    if len(country_code) != 2 or not country_code.isascii() or not country_code.isalpha():
        raise ToolError('国家代码须为两个英文字母，例如中国CN。')

    async def request():
        async with httpx.AsyncClient(timeout=8) as client:
            response = await client.get(
                'https://geocoding-api.open-meteo.com/v1/search',
                params={'name': city, 'count': 5, 'language': 'zh', 'countryCode': country_code},
            )
            response.raise_for_status()
            locations = response.json().get('results', [])
            if not locations:
                raise ToolError('未找到该城市，请尝试城市英文名或拼音，例如Hangzhou。')
            location = locations[0]
            response = await client.get(
                'https://api.open-meteo.com/v1/forecast',
                params={
                    'latitude': location['latitude'], 'longitude': location['longitude'],
                    'current': 'temperature_2m,relative_humidity_2m,apparent_temperature,weather_code,wind_speed_10m',
                    'daily': 'weather_code,temperature_2m_max,temperature_2m_min,precipitation_probability_max',
                    'timezone': 'auto', 'forecast_days': days,
                },
            )
            response.raise_for_status()
            data = response.json()
        current = data['current']
        daily = data['daily']
        return {
            'source': 'Open-Meteo', 'source_url': 'https://open-meteo.com/',
            'location': {
                'city': location['name'], 'province': location.get('admin1', ''),
                'country': location.get('country', country_code),
                'latitude': location['latitude'], 'longitude': location['longitude'],
            },
            'timezone': data['timezone'],
            'current': {
                'time': current['time'],
                'weather': WEATHER_CODES.get(current['weather_code'], '未知天气'),
                'temperature_c': current['temperature_2m'],
                'feels_like_c': current['apparent_temperature'],
                'humidity_percent': current['relative_humidity_2m'],
                'wind_kmh': current['wind_speed_10m'],
            },
            'forecast': [
                {'date': date,
                 'weather': WEATHER_CODES.get(daily['weather_code'][i], '未知天气'),
                 'min_c': daily['temperature_2m_min'][i],
                 'max_c': daily['temperature_2m_max'][i],
                 'rain_probability_percent': daily['precipitation_probability_max'][i]}
                for i, date in enumerate(daily['time'])
            ],
            'note': '当前天气为模式估算，预报从今天开始。请展示实际解析的城市、省份和数据时间；同名城市请先确认地点。',
        }

    try:
        return await asyncio.wait_for(request(), timeout=18)
    except (httpx.TimeoutException, asyncio.TimeoutError) as exc:
        raise ToolError('天气服务请求超时，请稍后重试。') from exc
    except httpx.HTTPError as exc:
        raise ToolError('无法连接天气数据服务，请稍后重试。') from exc
    except (KeyError, TypeError, ValueError, IndexError) as exc:
        raise ToolError('天气服务返回的数据不完整，请稍后重试。') from exc


@mcp.tool()
async def get_weather(
    city: Annotated[str, Field(min_length=1, max_length=100)],
    days: Annotated[int, Field(ge=1, le=7)] = 3,
    country_code: Annotated[str, Field(pattern='^[A-Za-z]{2}$')] = 'CN',
) -> dict:
    """查询城市当前天气和从今天起1到7天预报，返回温度、体感、湿度、风速和降雨概率。

    city填写城市名称，如杭州、Hangzhou、郑州，不要传整句问题。
    country_code默认CN；其他国家使用两位国家代码。days=3包含今天、明天、后天。
    问天气、降雨或出行穿衣时调用此工具获取数据，不要凭模型知识猜测天气。
    """
    return await fetch_weather(city, days, country_code)


if __name__ == '__main__':
    mcp.run(transport='stdio')
