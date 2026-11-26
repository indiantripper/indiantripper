(function(){
'use strict';
const quotes=JSON.parse(document.querySelector('[data-quotes]').getAttribute('data-quotes'));
if (!quotes.length) return;
const text=document.getElementById('quote-text'),author=document.getElementById('quote-author'),book=document.getElementById('quote-book'),back=document.getElementById('quote-back'),shuffle=document.getElementById('quote-shuffle');
let bag=[],history=[],cursor=-1;
function next(){if(!bag.length){bag=quotes.map((_,i)=>i);for(let i=bag.length-1;i>0;i--){let j=Math.floor(Math.random()*(i+1));[bag[i],bag[j]]=[bag[j],bag[i]];}if(history.length&&bag.at(-1)===history.at(-1)){[bag[0],bag[bag.length-1]]=[bag.at(-1),bag[0]];}}return bag.pop();}
function show(){const q=quotes[history[cursor]];text.textContent='“'+q.quote+'”';text.lang=/[\u0900-\u097f]/.test(q.quote)?'hi':'en';author.textContent=q.author;book.textContent=q.book;text.closest('figure').classList.toggle('long',q.quote.length>420);back.disabled=cursor===0;}
shuffle.addEventListener('click',()=>{if(cursor<history.length-1){cursor++;}else{history.push(next());cursor++;}show();});
back.addEventListener('click',()=>{if(cursor>0){cursor--;show();}});
history=[next()];cursor=0;show();shuffle.disabled=false;
})();
