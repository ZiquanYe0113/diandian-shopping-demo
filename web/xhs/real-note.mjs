export function mergeRealNotes(notes, incoming){
 const real=(incoming||[]).filter(n=>n?.real===true&&typeof n.note_id==='string'&&typeof n.text==='string');
 const byId=new Map();for(const n of [...real,...notes])if(!byId.has(n.note_id))byId.set(n.note_id,n);
 return [...byId.values()];
}
export function safeQrImage(value){return typeof value==='string'&&/^data:image\/(png|jpeg|webp);base64,[A-Za-z0-9+/=]+$/.test(value)?value:''}
export async function xhsRequest(url,options={},read=fetch){
 let response;try{response=await read(url,options)}catch{throw Error('连接中断，请检查本地服务后重试。')}
 let data;try{data=await response.json()}catch{throw Error('服务返回内容异常，请重试。')}
 if(!response.ok)throw Error(typeof data.detail==='string'?data.detail:'操作失败，请检查服务或重新分享链接。');
 return data;
}
