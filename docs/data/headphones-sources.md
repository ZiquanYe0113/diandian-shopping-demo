# 耳机资料来源与核验记录

参数核验日期2026-10-15；Sony价格补核日期2026-10-17（Australia/Brisbane）。8个真实型号/版本；8条中国官网标价快照，其中Apple四条保留2026-10-15记录，Sony四条于2026-10-17从官方购买页核对具体颜色SKU。均不是已支付成交价，所有库存未知。官方最长续航是特定条件的测试值，不是用户实际最低保证。海外同型号说明仅支持参数，不用于换算中国价格。

| ID | 型号/版本 | 中国官网价快照 | 参数与价格来源 |
|---|---|---|---|
| H001 | AirPods 5（USB-C 充电盒款） | 999元 | [参数](https://www.apple.com.cn/airpods-5/specs/) / [价格](https://www.apple.com.cn/shop/buy-airpods/airpods-5/mkfw4ch/a) |
| H002 | AirPods 5（配无线充电盒） | 1149元 | [参数](https://www.apple.com.cn/airpods-5/specs/) / [价格](https://www.apple.com.cn/shop/buy-airpods/airpods-5/mkft4ch/a) |
| H003 | AirPods Pro 3 | 1899元 | [参数](https://www.apple.com.cn/airpods-pro/specs/) / [价格](https://www.apple.com.cn/shop/buy-airpods/airpods-pro-3?product=mfhp4ch/a&step=select) |
| H004 | Sony WH-CH520 | 298元；粉红；WH-CH520/PZ；2026-10-17 | [参数](https://www.sonystyle.com.cn/products/headphone/wh_ch520/wh_ch520_feature.html) / [价格](https://www.sonystyle.com.cn/products/headphone/wh_ch520/wh_ch520_p.html) |
| H005 | Sony WH-CH720N | 654元；粉；WH-CH720N/PC；2026-10-17 | [参数](https://www.sonystyle.com.cn/products/headphone/wh_ch720n/wh_ch720n_feature.html) / [价格](https://www.sonystyle.com.cn/products/headphone/wh_ch720n/wh_ch720n_p.html) |
| H006 | Sony WF-C510 | 349元；黄；WF-C510/YZ；2026-10-17 | [参数](https://www.sony.com.cn/content/sonyportal/zh-cn/cms/newscenter/product/2024/240927.html) / [价格](https://www.sonystyle.com.cn/products/headphone/wf_c510/wf_c510_y.html) |
| H007 | Sony WF-C710N | 639元；粉；WF-C710N/PZ CN；2026-10-17 | [参数](https://www.sony.com.cn/content/sonyportal/zh-cn/cms/newscenter/product/2025/20250507-1.html) / [价格](https://www.sonystyle.com.cn/products/headphone/wf_c710n/wf_c710n_p.html?prior=feature) |
| H008 | AirPods Max 2（蓝色） | 3999元 | [参数](https://www.apple.com.cn/airpods-max/specs/) / [价格](https://www.apple.com.cn/shop/buy-airpods/airpods-max-2/mhwm4ch/a) |

## 处理原则

每项attributes保存value、unit、qualifier、source_quote、source_url、checked_at和verified；续航另保存mode。相同属性的不同模式不能字典覆盖。单次/总计分别使用battery_single/battery_total，含盒时长不作为单次。H007 AAC与SBC有不同续航，未指定编码器时采用更保守的同模式要求。

只有price_verified且有已知官方域名来源和报价原文的价格才进入生产目录。参考价不等于实付、活动价或实时成交。Sony官网动态价格经浏览器可见页面核验；price_source_quote保存非划线价原文，price_specification保存本次所选颜色及SKU，price_checked_at单独记录本次核验日，price_updated_at为快照观察日，不代表厂商调价日。币种人民币CNY，单位元/件。其他颜色和登录专属优惠未经逐一核验。

AirPods 5两种充电盒款为不同SKU；泛称不能确认具体版本。CH520/C510的通话降噪或被动隔音不视为聆听ANC。IP防护等级不自动推导游泳适用。

## 2026-10-17 Sony价格补核证据

网页文本抓取对动态购买页出现403或未渲染模板，不能直接当作无价格。改用官方商城浏览器页面，等商品加载完成后以可见截图同时核对型号、所选颜色和价格栏，未登录、未加购物车、未进入结算。4款`price_type`均为`中国官网标价快照`，`price_updated_at`与`price_checked_at`均为2026-10-17。

| ID | 购买页价格原文 | 同屏身份与所选颜色 | 同屏划线价（仅用于辨别价格栏，不作本次参考价） |
|---|---|---|---|
| H004 | `¥298` | `WH-CH520/PZ`；`WH-CH520 舒适高效头戴式耳机 粉红`；粉红选项有选中边框 | ¥499 |
| H005 | `¥654` | `WH-CH720N/PC`；`WH-CH720N 舒适高效头戴式降噪耳机 粉`；`已选：WH-CH720N 粉` | ¥899 |
| H006 | `¥349` | `WF-C510/YZ`；`WF-C510 轻巧舒适真无线耳机 黄`；黄选项有选中边框 | ¥499 |
| H007 | `¥639` | `WF-C710N/PZ CN`；`WF-C710N 休闲舒适真无线降噪耳机 粉`；`已选：WF-C710N 粉` | ¥849 |

H006从[官方耳机目录](https://www.sonystyle.com.cn/products/headphone/index.html)的WF-C510“去购买”进入`wf_c510_y.html`；猜测的`wf_c510_p.html`会重定向到耳机目录，不作为价格来源。H007目录卡当时显示689元，但所选粉色购买页明确为639元；采用具体SKU页，不能用目录默认款的价格覆盖所选颜色。

商城页脚解释划线价为厂商建议零售价，非划线价为厂商后台商品实时标价，并说明实际成交价以结算页面为准。本次只记录公开可见非划线标价，不推断会员价、补贴资格、可售库存或实付金额。价格可能变化，应重新打开对应链接核验。

历史交叉核验（不作为当前价格）：[2023-03-01官方发布稿附图](https://www.sony.com.cn/content/sonyportal/zh-cn/cms/newscenter/product/2023/20230301-1/_jcr_content/detail/image_1670645322.img.jpg/1678348666049.jpg)列WH-CH520建议零售价`RMB 499`、WH-CH720N `RMB 799`；[2024-09-27官方发布稿附图](https://www.sony.com.cn/content/sonyportal/zh-cn/cms/newscenter/product/2024/240927/_jcr_content/detail/image_250971475.img.jpg/1728707404658.jpg)列WF-C510建议零售价`499元`；[2025-05-07官方发布稿](https://www.sony.com.cn/content/sonyportal/zh-cn/cms/newscenter/product/2025/20250507-1.html)列WF-C710N冰透蓝899元，粉/白/黑849元。发布价与当前标价不能混用，CH720N初发稿也不能证明后来粉色SKU的建议零售价。

参数来源冲突记录：[2023发布稿](https://www.sony.com.cn/content/sonyportal/zh-cn/cms/newscenter/product/2023/20230301-1.html)旧脚注写WH-CH720N开降噪约30小时；现有商城对比表为开降噪约35小时。测试条件或资料版本差异未在本次价格补核中消解，保留已有商城属性证据，不以旧新闻稿静默覆盖，不把任一测试值说成用户续航保证。H007的AAC/SBC续航条件继续分别保留。本次未改产品ID、通用型号身份或参数属性。

修改前文件备份：`runtime/backups/20261017-price-audit/data/source/headphones.json`与`runtime/backups/20261017-price-audit/docs/data/headphones-sources.md`。

父线程独立复核截图（仅本机runtime，不随公开包分发）：
- H004：`runtime/research/headphone-prices-20261017/H004.png`
- H005：`runtime/research/headphone-prices-20261017/H005.png`
- H006：`runtime/research/headphone-prices-20261017/H006.png`
- H007：`runtime/research/headphone-prices-20261017/H007.png`
