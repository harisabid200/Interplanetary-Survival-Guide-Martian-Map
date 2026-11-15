import {projectionFunctions} from './coordinates.js';

export function marsSurfaceDistanceM(a,b,radiusM=3396190){
  const radians=Math.PI/180;
  const lat1=a[1]*radians,lat2=b[1]*radians;
  const dLat=lat2-lat1,dLon=(b[0]-a[0])*radians;
  const h=Math.sin(dLat/2)**2+Math.cos(lat1)*Math.cos(lat2)*Math.sin(dLon/2)**2;
  return 2*radiusM*Math.asin(Math.sqrt(Math.max(0,Math.min(1,h))));
}

/**
 * Filter real SIM 3464 map points using explicit user criteria. The 200 m
 * max-slope envelope contains the map's documented 100-200 m registration
 * offset. This is a terrain screen, never a safety or path-access guarantee.
 */
export function rankScienceStops(features,data,startLonLat,maxSlopeDeg,maxDistanceKm){
  if(!Array.isArray(startLonLat)||startLonLat.length!==2||!startLonLat.every(Number.isFinite))throw new Error('Set a valid starting coordinate first.');
  if(!Number.isFinite(maxSlopeDeg)||maxSlopeDeg<0||maxSlopeDeg>90)throw new Error('Enter a maximum buffered slope from 0 to 90 degrees.');
  if(!Number.isFinite(maxDistanceKm)||maxDistanceKm<=0||maxDistanceKm>1000)throw new Error('Enter a maximum straight-line range greater than 0 and at most 1,000 km.');
  const functions=projectionFunctions(data.region.crs);
  const [west,south,east,north]=data.region.bounds_m;
  const [pixelX,,originX,,pixelY,originY]=data.region.affine;
  const ranked=[];
  for(const feature of features){
    if(feature?.geometry?.type!=='Point'||feature.properties?.feature_type!=='small crater')continue;
    const [x,y]=feature.geometry.coordinates;
    const locationLonLat=functions.inverse([x,y]);
    const distanceM=marsSurfaceDistanceM(startLonLat,locationLonLat,data.region.crs.radius_m);
    if(distanceM>maxDistanceKm*1000)continue;
    // Require the complete 200 m uncertainty buffer to remain in measured terrain.
    const guardM=220;
    if(x-guardM<west||x+guardM>east||y-guardM<south||y+guardM>north)continue;
    const centerCol=Math.floor((x-originX)/pixelX);
    const centerRow=Math.floor((y-originY)/pixelY);
    const colRadius=Math.ceil(guardM/pixelX),rowRadius=Math.ceil(guardM/Math.abs(pixelY));
    let maximumSlope=0,cellCount=0,complete=true;
    for(let row=Math.max(0,centerRow-rowRadius);row<=Math.min(data.region.height-1,centerRow+rowRadius);row++){
      for(let col=Math.max(0,centerCol-colRadius);col<=Math.min(data.region.width-1,centerCol+colRadius);col++){
        const index=row*data.region.width+col;
        const mapPoint=[originX+(col+.5)*pixelX,originY+(row+.5)*pixelY];
        if(marsSurfaceDistanceM(locationLonLat,functions.inverse(mapPoint),data.region.crs.radius_m)>200)continue;
        cellCount++;
        if(!data.grids.valid[index]||!Number.isFinite(data.grids.slope[index])){complete=false;continue;}
        maximumSlope=Math.max(maximumSlope,data.grids.slope[index]);
      }
    }
    if(!complete||cellCount===0||maximumSlope>maxSlopeDeg)continue;
    ranked.push({feature,surface_distance_m:distanceM,uncertainty_radius_m:200,
      maximum_slope_within_uncertainty_buffer_deg:maximumSlope,buffer_cells:cellCount});
  }
  ranked.sort((a,b)=>a.surface_distance_m-b.surface_distance_m||a.maximum_slope_within_uncertainty_buffer_deg-b.maximum_slope_within_uncertainty_buffer_deg||a.feature.id.localeCompare(b.feature.id));
  return ranked;
}
